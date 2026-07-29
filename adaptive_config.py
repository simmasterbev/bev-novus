"""Generate the next Bev Novus experiment configuration from a result report."""

from __future__ import annotations

import argparse
import json
import math
import random
import re
from pathlib import Path


PARAMETERS = {
    "body_yield": (0.10, 0.98),
    "decay_rate": (0.00001, 0.01),
    "metabolism": (0.005, 0.08),
    "resource_regrowth": (0.001, 0.05),
    "body_strength": (0.25, 3.0),
    "resource_capacity": (0.25, 3.0),
}
INTEGER_PARAMETERS = {"resource_patches", "body_patches", "seed_interval"}
LABEL_RE = re.compile(r"yield=([0-9.eE+-]+),\s*decay=([0-9.eE+-]+)")
DEFAULTS = {
    "metabolism": 0.035, "resource_regrowth": 0.01, "body_strength": 1.5,
    "resource_capacity": 1.0,
}


def _rows(report: object) -> list[dict]:
    if isinstance(report, list):
        return [row for row in report if isinstance(row, dict)]
    if not isinstance(report, dict):
        raise ValueError("Result file must contain a JSON list or report object.")
    for key in ("results", "replays", "screening"):
        value = report.get(key)
        if isinstance(value, list):
            return [row for row in value if isinstance(row, dict)]
    raise ValueError("Could not find results, replays, or screening rows in the report.")


def _config(row: dict) -> dict:
    config = row.get("config") if isinstance(row.get("config"), dict) else {}
    config = {**config, **{name: row[name] for name in PARAMETERS if name in row}}
    match = LABEL_RE.search(str(row.get("label", "")))
    if match:
        config.setdefault("body_yield", float(match.group(1)))
        config.setdefault("decay_rate", float(match.group(2)))
    return config


def _score(row: dict) -> float:
    if row.get("finite") is False or "error" in row or row.get("live", 0) <= 0:
        return -1e9
    live = min(float(row.get("live", 0)) / 60.0, 1.0)
    body_mass = math.log1p(max(float(row.get("body_mass", 0)), 0.0)) / 8.0
    drift = float(row.get("mass_drift", 0.0) or 0.0)
    accounting = 1.0 / (1.0 + max(drift, 0.0) * 1000.0)
    births = min(float(row.get("births", 0)) / 10.0, 1.0)
    return 0.55 * live + 0.20 * min(body_mass, 1.0) + 0.20 * accounting + 0.05 * births


def _clamp(name: str, value: float) -> float:
    low, high = PARAMETERS[name]
    return max(low, min(high, value))


def build_next_config(report_path: Path, output_path: Path, *, count: int = 24,
                      elite_count: int = 6, seed: int = 7) -> dict:
    report = json.loads(report_path.read_text(encoding="utf-8"))
    candidates = []
    for row in _rows(report):
        config = _config(row)
        if "body_yield" not in config or "decay_rate" not in config:
            continue
        candidates.append({"score": _score(row), "config": config, "seed": row.get("seed")})
    candidates.sort(key=lambda item: item["score"], reverse=True)
    if not candidates:
        raise ValueError("No rows with body yield and decay rate were found.")

    rng = random.Random(seed)
    elites = candidates[:max(1, min(elite_count, len(candidates)))]
    configs = []
    for index in range(count):
        parent = elites[index % len(elites)]["config"]
        child = dict(parent)
        for name, (low, high) in PARAMETERS.items():
            value = float(parent.get(name, (low + high) / 2.0))
            if name == "decay_rate":
                value *= math.exp(rng.uniform(-0.55, 0.55))
            else:
                value += rng.gauss(0.0, (high - low) * 0.12)
            child[name] = _clamp(name, value)
        for name in INTEGER_PARAMETERS:
            if name in child:
                child[name] = int(round(child[name]))
        configs.append(child)

    # Keep the first entries as exact elites so the next run always contains controls.
    for index, elite in enumerate(elites[:count]):
        configs[index] = {name: elite["config"].get(name, DEFAULTS.get(name, (PARAMETERS[name][0] + PARAMETERS[name][1]) / 2.0))
                          for name in PARAMETERS}
    top = [{"score": item["score"], "seed": item["seed"], "config": item["config"]} for item in elites]
    generation = int(report.get("generation", 0)) + 1 if isinstance(report, dict) else 1
    output = {
        "schema": "bev-novus-adaptive-config-v1",
        "generation": generation,
        "source_report": str(report_path),
        "seed": seed,
        "candidate_count": len(candidates),
        "elite_count": len(elites),
        "top_candidates": top,
        "configs": configs,
        "gui_defaults": {
            "Engine": "Particle hybrid",
            "Body yield": ",".join(f"{value['body_yield']:.5g}" for value in configs[:min(8, len(configs))]),
            "Particle decay": ",".join(f"{value['decay_rate']:.5g}" for value in configs[:min(8, len(configs))]),
            "GPU batch": "32",
            "Broad configs": str(count),
        },
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(output, indent=2), encoding="utf-8")
    return output


def main() -> None:
    parser = argparse.ArgumentParser(description="Create the next adaptive Bev Novus configuration.")
    parser.add_argument("report", type=Path)
    parser.add_argument("--out", type=Path, default=Path("Results/adaptive-next.json"))
    parser.add_argument("--count", type=int, default=24)
    parser.add_argument("--elites", type=int, default=6)
    parser.add_argument("--seed", type=int, default=7)
    args = parser.parse_args()
    result = build_next_config(args.report, args.out, count=args.count, elite_count=args.elites, seed=args.seed)
    print(f"generation {result['generation']}: {len(result['configs'])} configs from {result['candidate_count']} candidates")
    print(f"wrote {args.out}")


if __name__ == "__main__":
    main()
