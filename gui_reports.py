"""Filesystem operations for GUI-managed experiment reports."""

from __future__ import annotations

import json
import time
from pathlib import Path


_REPORT_VALIDATION_CACHE: dict[str, tuple[int, int, bool]] = {}


def _is_loadable_report(path: Path) -> bool:
    try:
        stat = path.stat()
    except OSError:
        return False
    key = str(path.resolve())
    signature = (stat.st_mtime_ns, stat.st_size)
    cached = _REPORT_VALIDATION_CACHE.get(key)
    if cached and cached[:2] == signature:
        return cached[2]
    try:
        read_report(path)
    except (OSError, ValueError, json.JSONDecodeError):
        valid = False
    else:
        valid = True
    _REPORT_VALIDATION_CACHE[key] = (*signature, valid)
    return valid


def list_report_paths(results_dir: Path) -> list[Path]:
    candidates = [path for path in results_dir.glob("*.json") if path.name != "adaptive-next.json"]
    candidates += list((results_dir / "adaptive-campaign").glob("*.json"))
    paths = [path for path in candidates if _is_loadable_report(path)]
    return sorted(paths, key=lambda path: path.stat().st_mtime_ns if path.exists() else 0, reverse=True)


def read_report(path: Path) -> dict:
    report = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(report, dict):
        raise ValueError("That JSON file is not a report object.")
    rows = report.get("replays") or report.get("results") or report.get("screening") or []
    if not isinstance(rows, list) or not rows:
        raise ValueError("That JSON file does not contain report rows.")
    return report


def archive_report(results_dir: Path, prefix: str, report: dict) -> Path:
    results_dir.mkdir(parents=True, exist_ok=True)
    path = results_dir / f"{prefix}-{time.strftime('%Y%m%d-%H%M%S')}-{time.time_ns() % 1000000:06d}.json"
    path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    return path


def delete_report(path: Path, results_dir: Path) -> None:
    allowed = {results_dir.resolve(), (results_dir / "adaptive-campaign").resolve()}
    resolved = path.resolve()
    if resolved.parent not in allowed or resolved.suffix.lower() != ".json":
        raise ValueError("Only GUI report files under Results can be deleted.")
    resolved.unlink()
