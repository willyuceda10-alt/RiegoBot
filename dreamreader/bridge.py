from __future__ import annotations

import json
import os
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class BridgeResult:
    success: bool
    exit_code: int
    executable: str | None
    command: list[str]
    stdout: str
    stderr: str
    latest_session: str | None
    session_summary: dict[str, Any] | None

    def to_dict(self) -> dict[str, Any]:
        return {
            "success": self.success,
            "exitCode": self.exit_code,
            "executable": self.executable,
            "command": self.command,
            "stdout": self.stdout,
            "stderr": self.stderr,
            "latestSession": self.latest_session,
            "sessionSummary": self.session_summary,
        }


def _find_powershell() -> str | None:
    return shutil.which("powershell.exe") or shutil.which("powershell")


def _latest_session(project_root: Path) -> Path | None:
    output_root = project_root / "output"
    if not output_root.exists():
        return None
    sessions = list(output_root.rglob("session.json"))
    if not sessions:
        return None
    latest = max(sessions, key=lambda path: path.stat().st_mtime)
    return latest.parent


def _read_session_summary(session_dir: Path | None) -> dict[str, Any] | None:
    if session_dir is None:
        return None
    path = session_dir / "session.json"
    if not path.is_file():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError):
        return None


def invoke_readonly_bridge(
    project_root: Path,
    extraction_mode: str = "NORMALIZED",
    dream_root: Path | None = None,
) -> BridgeResult:
    powershell = _find_powershell()
    script = project_root / "scripts" / "INICIAR_V1_3.ps1"

    if powershell is None:
        return BridgeResult(False, 127, None, [], "", "PowerShell no fue encontrado.", None, None)

    if not script.is_file():
        return BridgeResult(
            False, 2, powershell, [], "", f"No existe el puente MDB: {script}", None, None
        )

    mode = extraction_mode.upper()
    if mode not in {"DISCOVERY", "NORMALIZED"}:
        raise ValueError("extraction_mode must be DISCOVERY or NORMALIZED")

    command = [
        powershell,
        "-NoProfile",
        "-ExecutionPolicy",
        "Bypass",
        "-File",
        str(script),
        "-BaseDirectory",
        str(project_root),
        "-ExtractionMode",
        mode,
    ]

    environment = os.environ.copy()
    if dream_root is not None:
        environment["RIEGOBOT_DREAM_ROOT"] = str(dream_root)

    before = set((project_root / "output").rglob("session.json")) if (project_root / "output").exists() else set()

    completed = subprocess.run(
        command,
        cwd=str(project_root),
        env=environment,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )

    after = set((project_root / "output").rglob("session.json")) if (project_root / "output").exists() else set()
    new_sessions = after - before
    latest = (
        max(new_sessions, key=lambda path: path.stat().st_mtime).parent
        if new_sessions
        else _latest_session(project_root)
    )
    summary = _read_session_summary(latest)

    semantic_success = completed.returncode == 0
    exit_code = completed.returncode

    if summary is not None:
        errors = summary.get("Errors") or []
        dreams_discovered = int(summary.get("DreamsDiscovered") or 0)
        if errors or dreams_discovered == 0:
            semantic_success = False
            if exit_code == 0:
                exit_code = 5

    return BridgeResult(
        semantic_success,
        exit_code,
        powershell,
        command,
        completed.stdout.strip(),
        completed.stderr.strip(),
        str(latest) if latest else None,
        summary,
    )
