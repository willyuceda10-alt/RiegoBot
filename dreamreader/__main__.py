from __future__ import annotations

import argparse
import json

from . import PROJECT_ROOT, __version__
from .bridge import invoke_readonly_bridge
from .config import load_config
from .discovery import discover_dreams, get_discovery_info
from .runtime import write_discovery_outputs
from .session import create_session
from .validation import python_version_ok


def main() -> int:
    parser = argparse.ArgumentParser(description="DreamReader portable control plane")
    parser.add_argument(
        "command",
        choices=("discovery", "extract", "doctor"),
        nargs="?",
        default="discovery",
    )
    args = parser.parse_args()

    if not python_version_ok():
        print("DreamReader requires Python 3.11 or later.")
        return 2

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
        if not discovery_info["rootExists"]:
            payload["warning"] = (
                "La carpeta de Dream configurada no existe. "
                "Use config/config.local.json o la variable RIEGOBOT_DREAM_ROOT."
            )
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

    if not discovery_info["rootExists"]:
        payload["warning"] = (
            "No se encontro la carpeta de bases Dream. "
            f"Ruta resuelta: {discovery_info['rootPath']}"
        )
    elif not dreams:
        payload["warning"] = (
            "La carpeta existe, pero no se encontraron archivos que coincidan con "
            f"{discovery_info['pattern']}."
        )

    if args.command == "extract":
        bridge = invoke_readonly_bridge(PROJECT_ROOT, "NORMALIZED")
        payload["mdbBridge"] = bridge.to_dict()
        if not bridge.success:
            payload["error"] = (
                "El bridge MDB PowerShell no termino correctamente. "
                "Revise stdout/stderr y el log generado."
            )
            print(json.dumps(payload, indent=2, ensure_ascii=False))
            return bridge.exit_code or 1

    print(json.dumps(payload, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
