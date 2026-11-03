from __future__ import annotations

import getpass
import json
import re
import secrets
import socket
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _safe(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9_-]", "_", value).strip("_") or "unknown"


@dataclass(frozen=True)
class SessionContext:
    session_id: str
    site_id: str
    collector_id: str
    host: str
    user: str
    started_at: str
    output_dir: Path
    log_file: Path

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["output_dir"] = str(self.output_dir)
        data["log_file"] = str(self.log_file)
        return data


def build_session_id(now: datetime | None = None) -> str:
    current = now or datetime.now()
    return (
        f"{current:%Y%m%d_%H%M%S}_"
        f"{_safe(socket.gethostname())}_"
        f"{_safe(getpass.getuser())}_"
        f"{secrets.token_hex(4)}"
    )


def create_session(project_root: Path, config: dict[str, Any]) -> SessionContext:
    site_id = _safe(str(config["collector"]["siteId"]))
    collector_id = _safe(str(config["collector"]["collectorId"]))
    session_id = build_session_id()
    output_dir = project_root / "output" / site_id / collector_id / session_id
    log_dir = project_root / "logs" / site_id / collector_id
    output_dir.mkdir(parents=True, exist_ok=False)
    log_dir.mkdir(parents=True, exist_ok=True)
    context = SessionContext(
        session_id=session_id,
        site_id=site_id,
        collector_id=collector_id,
        host=_safe(socket.gethostname()),
        user=_safe(getpass.getuser()),
        started_at=datetime.now(timezone.utc).isoformat(),
        output_dir=output_dir,
        log_file=log_dir / f"DreamReader_{session_id}.log",
    )
    (output_dir / "session_context.json").write_text(
        json.dumps(context.to_dict(), indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    return context
