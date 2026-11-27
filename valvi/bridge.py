"""Bounded, local-only compatibility probe for an authorized test MDB copy."""
from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

PROVIDERS = ("Microsoft.Jet.OLEDB.4.0", "Microsoft.ACE.OLEDB.16.0", "Microsoft.ACE.OLEDB.12.0")
STATUSES = {"PROVIDERS_CHECKED", "FIXTURE_READ", "FIXTURE_UNREADABLE", "INVALID_FIXTURE", "PROVIDER_CHECK_FAILED"}


class BridgeError(RuntimeError):
    """Sanitized compatibility error; never includes subprocess output or paths."""


def parse_probe(raw: str) -> dict:
    try:
        data = json.loads(raw.lstrip("\ufeff"))
    except (ValueError, AttributeError):
        raise BridgeError("Invalid bridge JSON.") from None
    keys = {"status", "providers", "process_bits", "fixture_checked", "table_count", "read_only"}
    if not isinstance(data, dict) or set(data) != keys:
        raise BridgeError("Unexpected bridge response fields.")
    if not isinstance(data["status"], str) or data["status"] not in STATUSES:
        raise BridgeError("Unknown bridge status.")
    providers = data["providers"]
    if (not isinstance(providers, list) or any(not isinstance(p, str) or p not in PROVIDERS for p in providers)
            or len(set(providers)) != len(providers)):
        raise BridgeError("Invalid provider list.")
    if type(data["process_bits"]) is not int or data["process_bits"] not in (32, 64):
        raise BridgeError("Invalid process architecture.")
    if data["read_only"] is not True or type(data["fixture_checked"]) is not bool:
        raise BridgeError("Invalid read-only contract.")
    count = data["table_count"]
    if data["status"] == "FIXTURE_READ":
        if not data["fixture_checked"] or type(count) is not int or count < 0:
            raise BridgeError("Invalid fixture result.")
    elif count is not None or data["fixture_checked"] != (data["status"] == "FIXTURE_UNREADABLE"):
        raise BridgeError("Inconsistent fixture status.")
    return data


def run_probe(command: list[str], *, runner=subprocess.run, timeout: int = 30) -> dict:
    try:
        result = runner(command, capture_output=True, text=False, timeout=timeout, check=False)
    except subprocess.TimeoutExpired:
        raise BridgeError("Local probe timed out.") from None
    except OSError:
        raise BridgeError("Local PowerShell could not be run.") from None
    if result.returncode != 0:
        raise BridgeError(f"Local PowerShell exited with code {result.returncode}; check authorized execution policy and dependencies.")
    # Windows PowerShell can emit localized diagnostics in an OEM/ANSI encoding,
    # including before our script sets UTF-8. Never decode stderr as UTF-8.
    # Only successful stdout participates in the strict JSON contract.
    try:
        raw = result.stdout.decode("utf-8-sig")
    except (UnicodeError, AttributeError):
        raise BridgeError("Successful PowerShell output was not valid UTF-8.") from None
    return parse_probe(raw)


def probe_local(fixture: Path | None = None) -> dict:
    if os.name != "nt":
        raise BridgeError("MDB compatibility probe requires Windows.")
    system_root = os.environ.get("SystemRoot")
    if not system_root:
        raise BridgeError("Windows system directory unavailable.")
    exe = Path(system_root) / "System32" / "WindowsPowerShell" / "v1.0" / "powershell.exe"
    script = Path(__file__).resolve().parent.parent / "scripts" / "VALVI_MDB_PROBE.ps1"
    command = [str(exe), "-NoProfile", "-NonInteractive", "-File", str(script)]
    if fixture is not None:
        command.extend(["-Fixture", str(fixture)])
    return run_probe(command)
