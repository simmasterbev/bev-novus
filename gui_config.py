"""Small JSON-backed configuration library for the experiment GUI."""

from __future__ import annotations

import json
import re
from pathlib import Path


CONFIG_DIR = Path(__file__).with_name("Results") / "configs"
NAME_RE = re.compile(r"[^A-Za-z0-9._ -]+")


def _path(name: str) -> Path:
    clean = NAME_RE.sub("", name).strip(" .")
    if not clean:
        raise ValueError("Enter a configuration name.")
    return CONFIG_DIR / f"{clean}.json"


def list_presets() -> list[str]:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    return sorted(path.stem for path in CONFIG_DIR.glob("*.json"))


def save_preset(name: str, data: dict) -> Path:
    path = _path(name)
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")
    return path


def load_preset(name: str) -> dict:
    path = _path(name)
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict) or data.get("schema") != "bev-novus-gui-config-v1":
        raise ValueError("That file is not a Bev Novus GUI configuration.")
    return data


def delete_preset(name: str) -> None:
    _path(name).unlink(missing_ok=True)
