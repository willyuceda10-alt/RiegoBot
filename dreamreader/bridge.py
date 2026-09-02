from __future__ import annotations

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

    def to_dict(self) -> dict[str, Any]:
        return {
            "success": self.success,
            "exitCode": self.exit_code,
            "executable": self.executable,
            "command": self.command,
            "stdout": self.stdout,
            "stderr": self.stderr,
            "latestSession": self.latest_session,
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


def invoke_readonly_bridge(
    project_root: Path,
    extraction_mode: str = "NORMALIZED",
) -> BridgeResult:
    powershell = _find_powershell()
    script = project_root / "scripts" / "INICIAR_V1_3.ps1"

    if powershell is None:
        return BridgeResult(
            success=False,
            exit_code=127,
            executable=None,
            command=[],
            stdout="",
            stderr="PowerShell no fue encontrado.",
            latest_session=None,
        )

    if not script.is_file():
        return BridgeResult(
            success=False,
            exit_code=2,
            executable=powershell,
            command=[],
            stdout="",
            stderr=f"No existe el puente MDB: {script}",
            latest_session=None,
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

    completed = subprocess.run(
        command,
        cwd=str(project_root),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )

    latest = _latest_session(project_root)

    return BridgeResult(
        success=completed.returncode == 0,
        exit_code=completed.returncode,
        executable=powershell,
        command=command,
        stdout=completed.stdout.strip(),
        stderr=completed.stderr.strip(),
        latest_session=str(latest) if latest else None,
    )
