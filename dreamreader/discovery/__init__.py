from __future__ import annotations

import fnmatch
import os
from pathlib import Path
from typing import Any


ENV_DREAM_ROOT = "RIEGOBOT_DREAM_ROOT"


def _candidate_roots(project_root: Path, configured_path: str) -> list[tuple[str, Path]]:
    configured = Path(configured_path)
    candidates: list[tuple[str, Path]] = []

    override = os.environ.get(ENV_DREAM_ROOT, "").strip()
    if override:
        candidates.append(("environment", Path(override)))

    configured_resolved = (
        configured
        if configured.is_absolute()
        else (project_root / configured).resolve()
    )
    candidates.append(("config", configured_resolved))

    # Portable fallbacks relative to the project location. These avoid
    # user-specific absolute paths and cover common extracted-folder layouts.
    parent = project_root.parent
    fallbacks = [
        ("auto:project/Dream", project_root / "Dream"),
        ("auto:sibling/Dream", parent / "Dream"),
        ("auto:sibling/Dream_Realtime/Dream", parent / "Dream_Realtime" / "Dream"),
        ("auto:sibling/Dream_Realtime", parent / "Dream_Realtime"),
    ]
    candidates.extend(fallbacks)

    seen: set[str] = set()
    unique: list[tuple[str, Path]] = []
    for source, candidate in candidates:
        resolved = candidate.resolve()
        key = str(resolved).lower()
        if key not in seen:
            seen.add(key)
            unique.append((source, resolved))
    return unique


def resolve_discovery_root(
    project_root: Path,
    config: dict[str, Any],
) -> tuple[str, Path]:
    configured_path = config["discovery"]["rootPath"]
    pattern = config["discovery"]["dreamPattern"]

    candidates = _candidate_roots(project_root, configured_path)

    # Prefer a folder that actually contains Dream databases.
    for source, root in candidates:
        if root.is_dir() and any(
            item.is_file() and fnmatch.fnmatch(item.name.lower(), pattern.lower())
            for item in root.iterdir()
        ):
            return source, root

    # If no candidate contains matches, still prefer an existing configured or
    # environment directory so diagnostics can distinguish empty vs missing.
    for source, root in candidates:
        if source in {"environment", "config"} and root.is_dir():
            return source, root

    # Fall back to configured path for a deterministic diagnostic.
    for source, root in candidates:
        if source == "config":
            return source, root

    return candidates[0]


def get_discovery_info(project_root: Path, config: dict[str, Any]) -> dict[str, Any]:
    source, root = resolve_discovery_root(project_root, config)
    pattern = config["discovery"]["dreamPattern"]

    matches: list[str] = []
    if root.is_dir():
        matches = sorted(
            item.name
            for item in root.iterdir()
            if item.is_file()
            and fnmatch.fnmatch(item.name.lower(), pattern.lower())
        )

    return {
        "rootPath": str(root),
        "rootExists": root.is_dir(),
        "pattern": pattern,
        "source": source,
        "environmentVariable": ENV_DREAM_ROOT,
        "matchingFiles": matches,
        "matchingFileCount": len(matches),
        "candidatesChecked": [
            {"source": candidate_source, "path": str(candidate_path)}
            for candidate_source, candidate_path in _candidate_roots(
                project_root,
                config["discovery"]["rootPath"],
            )
        ],
    }


def discover_dreams(project_root: Path, config: dict[str, Any]) -> list[dict[str, Any]]:
    _, root = resolve_discovery_root(project_root, config)
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
