from __future__ import annotations

import argparse
import json
import re
import secrets
import socket
from datetime import datetime

from . import PROJECT_ROOT, __version__
from .config import load_config
from .discovery import discover_dreams
from .validation import python_version_ok


def _safe(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9_-]", "_", value) or "unknown"


def build_session_id() -> str:
    return f"{datetime.now():%Y%m%d_%H%M%S}_{_safe(socket.gethostname())}_{_safe(__import__('getpass').getuser())}_{secrets.token_hex(3)}"


def main() -> int:
    parser = argparse.ArgumentParser(description="DreamReader portable control plane")
    parser.add_argument("command", choices=("discovery", "extract"), nargs="?", default="discovery")
    args = parser.parse_args()
    if not python_version_ok():
        print("DreamReader requires Python 3.11 or later.")
        return 2
    config = load_config(PROJECT_ROOT)
    payload = {"version": __version__, "projectRoot": str(PROJECT_ROOT), "collector": config["collector"], "sessionIdPreview": build_session_id(), "dreams": discover_dreams(PROJECT_ROOT, config)}
    if args.command == "extract":
        payload["notice"] = "MDB extraction remains on the tested PowerShell bridge in this migration phase."
    print(json.dumps(payload, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
