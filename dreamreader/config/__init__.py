from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def _merge(shared: dict[str, Any], local: dict[str, Any]) -> dict[str, Any]:
    result = dict(shared)
    for key, value in local.items():
        result[key] = _merge(result[key], value) if isinstance(value, dict) and isinstance(result.get(key), dict) else value
    return result


def load_config(project_root: Path) -> dict[str, Any]:
    config_dir = project_root / "config"
    shared = json.loads((config_dir / "config.json").read_text(encoding="utf-8"))
    local_path = config_dir / "config.local.json"
    return _merge(shared, json.loads(local_path.read_text(encoding="utf-8")) if local_path.exists() else {})
