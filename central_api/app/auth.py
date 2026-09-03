from __future__ import annotations

import hmac
import json

from fastapi import Header, HTTPException

from .settings import load_settings


def _collector_keys() -> dict[str, str]:
    settings = load_settings()
    raw = getattr(settings, "collector_keys_json", None)
    if not raw:
        return {}
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        return {}
    if not isinstance(parsed, dict):
        return {}
    return {
        str(key): str(value)
        for key, value in parsed.items()
        if key and value
    }


def require_collector_key(
    collector_id: str,
    supplied_key: str | None,
) -> None:
    keys = _collector_keys()
    expected = keys.get(collector_id)
    if expected is None:
        raise HTTPException(status_code=401, detail="Collector is not authorized.")
    if supplied_key is None or not hmac.compare_digest(expected, supplied_key):
        raise HTTPException(status_code=401, detail="Invalid collector credentials.")
