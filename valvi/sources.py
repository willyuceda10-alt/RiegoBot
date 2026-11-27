"""Validate private source configuration without accessing any network or MDB."""
from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from pathlib import Path, PureWindowsPath

IDENTIFIER = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]{0,63}\Z")


class ConfigError(ValueError):
    """Configuration error that never includes private path values."""


@dataclass(frozen=True)
class Source:
    source_id: str
    site_id: str
    folder: str
    enabled: bool
    poll_seconds: int


def default_config_path() -> Path:
    local = os.environ.get("LOCALAPPDATA")
    base = Path(local) if local else Path.home() / ".config"
    return base / "Valvi" / "sources.json"


def valid_folder(value: object) -> bool:
    if not isinstance(value, str) or not value.strip() or value != value.strip():
        return False
    if any(c in value for c in '*?"<>|\x00') or any(ord(c) < 32 for c in value):
        return False
    if value.startswith(("\\\\?\\", "\\\\.\\")):
        return False
    path = PureWindowsPath(value)
    if path.drive.startswith("\\\\"):
        share = path.drive[2:].split("\\")
        if len(share) != 2 or not all(share):
            return False
    return path.is_absolute() and ".." not in path.parts


def parse_sources(document: object) -> tuple[Source, ...]:
    if not isinstance(document, dict) or set(document) != {"readOnly", "sources"}:
        raise ConfigError("Expected only readOnly and sources at the top level.")
    if document["readOnly"] is not True:
        raise ConfigError("readOnly must be true.")
    items = document["sources"]
    if not isinstance(items, list):
        raise ConfigError("sources must be an array.")
    sources = []
    ids = set()
    folders = set()
    keys = {"sourceId", "siteId", "folder", "enabled", "pollSeconds"}
    for index, item in enumerate(items, 1):
        prefix = f"Source {index}: "
        if not isinstance(item, dict) or set(item) != keys:
            raise ConfigError(prefix + "invalid or unexpected fields.")
        source_id, site_id = item["sourceId"], item["siteId"]
        if any(not isinstance(v, str) or not IDENTIFIER.fullmatch(v)
               for v in (source_id, site_id)):
            raise ConfigError(prefix + "invalid identifier.")
        if source_id.casefold() in ids:
            raise ConfigError(prefix + "duplicate sourceId.")
        folder = item["folder"]
        if not valid_folder(folder):
            raise ConfigError(prefix + "expected an explicit absolute Windows folder.")
        canonical = str(PureWindowsPath(folder)).casefold()
        if canonical in folders:
            raise ConfigError(prefix + "duplicate folder.")
        enabled = item["enabled"]
        seconds = item["pollSeconds"]
        if type(enabled) is not bool:
            raise ConfigError(prefix + "enabled must be a boolean.")
        if type(seconds) is not int or not 30 <= seconds <= 3600:
            raise ConfigError(prefix + "pollSeconds must be an integer from 30 to 3600.")
        ids.add(source_id.casefold())
        folders.add(canonical)
        sources.append(Source(source_id, site_id, folder, enabled, seconds))
    return tuple(sources)


def load_sources(path: Path) -> tuple[Source, ...]:
    try:
        document = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, UnicodeError, ValueError):
        raise ConfigError("Cannot read configuration as JSON.") from None
    return parse_sources(document)


def summary(sources: tuple[Source, ...]) -> dict:
    enabled = sum(s.enabled for s in sources)
    return {
        "configuration_valid": True,
        "sources": len(sources),
        "enabled": enabled,
        "disabled": len(sources) - enabled,
        "read_only": True,
        "network_checked": False,
        "database_read": False,
        "monitoring_started": False,
    }
