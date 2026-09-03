from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    environment: str
    database_url: str | None
    allow_test_replay: bool
    version: str


def _as_bool(value: str | None, default: bool = False) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def load_settings() -> Settings:
    return Settings(
        environment=os.getenv("RIEGOBOT_ENVIRONMENT", "development"),
        database_url=os.getenv("RIEGOBOT_DATABASE_URL"),
        allow_test_replay=_as_bool(os.getenv("RIEGOBOT_ALLOW_TEST_REPLAY"), True),
        version=os.getenv("RIEGOBOT_VERSION", "2.0.0-alpha"),
    )
