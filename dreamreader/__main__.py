from __future__ import annotations

import argparse
import json
from pathlib import Path

from . import PROJECT_ROOT, __version__
from .bridge import invoke_readonly_bridge
from .config import load_config
from .discovery import discover_dreams, get_discovery_info
from .runtime import write_discovery_outputs
from .query import build_romeo_query
from .session import create_session
from .validation import python_version_ok


def main() -> int:
    parser = argparse.ArgumentParser(description="DreamReader portable control plane")
    parser.add_argument(
        "command",
        choices=("discovery", "extract", "extract-candidates", "romeo", "doctor"),
        nargs="?",
        default="discovery",
    )
    parser.add_argument("target", nargs="?")
    args = parser.parse_args()

    if not python_version_ok():
        print("DreamReader requires Python 3.11 or later.")
        return 2

    if args.command == "romeo":
        if args.target is None or not str(args.target).isdigit():
            print(json.dumps({"success": False, "error": "Use: python -m dreamreader romeo <numero>"}, indent=2, ensure_ascii=False))
            return 2
        payload = build_romeo_query(PROJECT_ROOT, str(args.target))
        print(json.dumps(payload, indent=2, ensure_ascii=False))
        return 0 if payload.get("success") else 6

    config = load_config(PROJECT_ROOT)
    discovery_info = get_discovery_info(PROJECT_ROOT, config)

    if args.command == "doctor":
        payload = {
            "version": __version__,
            "projectRoot": str(PROJECT_ROOT),
            "collector": config["collector"],
            "python": "OK",
            "portableRoot": True,
            "readOnly": bool(config.get("readOnly", False)),
            "discovery": discovery_info,
        }
        if discovery_info["matchingFileCount"] == 0:
            payload["warning"] = "No se encontraron bases Dream para lectura."
        print(json.dumps(payload, indent=2, ensure_ascii=False))
        return 0

    session = create_session(PROJECT_ROOT, config)
    dreams = discover_dreams(PROJECT_ROOT, config)
    write_discovery_outputs(session.output_dir, dreams)

    payload = {
        "version": __version__,
        "projectRoot": str(PROJECT_ROOT),
        "collector": config["collector"],
        "session": session.to_dict(),
        "discovery": discovery_info,
        "dreams": dreams,
    }

    if discovery_info["matchingFileCount"] == 0:
        payload["warning"] = (
            "No se encontraron bases Dream. "
            f"Ruta resuelta: {discovery_info['rootPath']}"
        )

    if args.command in {"extract", "extract-candidates"}:
        if not dreams:
            payload["error"] = (
                "Extraccion cancelada: no hay controladores Dream disponibles. "
                "No se ejecutara el bridge MDB."
            )
            print(json.dumps(payload, indent=2, ensure_ascii=False))
            return 5

        bridge = invoke_readonly_bridge(
            PROJECT_ROOT,
            "NORMALIZED",
            Path(discovery_info["rootPath"]),
            allow_candidate_mappings=args.command == "extract-candidates",
        )
        payload["candidateMappingsEnabled"] = args.command == "extract-candidates"
        payload["mdbBridge"] = bridge.to_dict()
        if not bridge.success:
            payload["error"] = (
                "El bridge MDB no produjo una sesion valida. "
                "Revise sessionSummary, stdout/stderr y los logs."
            )
            print(json.dumps(payload, indent=2, ensure_ascii=False))
            return bridge.exit_code or 1

    print(json.dumps(payload, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
