from __future__ import annotations

import fnmatch
from pathlib import Path
from typing import Any


def resolve_path(project_root: Path, configured_path: str) -> Path:
    path = Path(configured_path)
    return path if path.is_absolute() else (project_root / path).resolve()


def discover_dreams(project_root: Path, config: dict[str, Any]) -> list[dict[str, Any]]:
    root = resolve_path(project_root, config["discovery"]["rootPath"])
    configured = {str(item["dreamId"]): item for item in config.get("dreams", [])}
    result: list[dict[str, Any]] = []
    for path in sorted(root.iterdir()) if root.is_dir() else []:
        if not path.is_file() or not fnmatch.fnmatch(path.name.lower(), config["discovery"]["dreamPattern"].lower()):
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
        result.append({"collectorId": config["collector"]["collectorId"], "siteId": site_id, "dreamKey": f"{site_id}-DREAM-{dream_id}", "dreamId": dream_id, "dreamName": item.get("name", f"Dream {dream_id}"), "databasePath": str(path), "status": "CONFIGURED" if item and enabled else "DISABLED" if item else "DISCOVERED"})
    found = {r["dreamId"] for r in result}
    for dream_id, item in configured.items():
        if dream_id not in found:
            site_id = config["collector"]["siteId"]
            result.append({"collectorId": config["collector"]["collectorId"], "siteId": site_id, "dreamKey": f"{site_id}-DREAM-{dream_id}", "dreamId": dream_id, "dreamName": item.get("name", f"Dream {dream_id}"), "databasePath": str(root / f"Dream{dream_id}_1.mdb"), "status": "UNKNOWN" if item.get("enabled", True) else "DISABLED"})
    return result
