from __future__ import annotations

import fnmatch
import os
from pathlib import Path
from typing import Any


ENV_DREAM_ROOT = "RIEGOBOT_DREAM_ROOT"


def resolve_path(project_root: Path, configured_path: str) -> Path:
    override = os.environ.get(ENV_DREAM_ROOT, "").strip()
    raw_path = override or configured_path
    path = Path(raw_path)
    return path if path.is_absolute() else (project_root / path).resolve()


def get_discovery_info(project_root: Path, config: dict[str, Any]) -> dict[str, Any]:
    root = resolve_path(project_root, config["discovery"]["rootPath"])
    pattern = config["discovery"]["dreamPattern"]
    return {
        "rootPath": str(root),
        "rootExists": root.is_dir(),
        "pattern": pattern,
        "source": "environment" if os.environ.get(ENV_DREAM_ROOT, "").strip() else "config",
        "environmentVariable": ENV_DREAM_ROOT,
    }


def discover_dreams(project_root: Path, config: dict[str, Any]) -> list[dict[str, Any]]:
    root = resolve_path(project_root, config["discovery"]["rootPath"])
    configured = {str(item["dreamId"]): item for item in config.get("dreams", [])}
    result: list[dict[str, Any]] = []

    if not root.is_dir():
        return result

    for path in sorted(root.iterdir()):
        if not path.is_file() or not fnmatch.fnmatch(
            path.name.lower(),
            config["discovery"]["dreamPattern"].lower(),
        ):
            continue

        stem = path.stem
        if not stem.lower().startswith("dream") or "_" not in stem:
            continue

        dream_id = stem[5:].split("_", 1)[0]
        if not dream_id.isdecimal():
            continue

        item = configured.get(dream_id, {})
        enabled = item.get("enabled", True)
        site_id = config["collector"]["siteId"]

        result.append(
            {
                "collectorId": config["collector"]["collectorId"],
                "siteId": site_id,
                "dreamKey": f"{site_id}-DREAM-{dream_id}",
                "dreamId": dream_id,
                "dreamName": item.get("name", f"Dream {dream_id}"),
                "databasePath": str(path),
                "status": (
                    "CONFIGURED"
                    if item and enabled
                    else "DISABLED"
                    if item
                    else "DISCOVERED"
                ),
            }
        )

    return result
