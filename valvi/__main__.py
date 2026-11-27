import argparse
import json
from pathlib import Path

from .bridge import BridgeError, probe_local
from .sources import ConfigError, default_config_path, load_sources, summary


def main() -> int:
    parser = argparse.ArgumentParser(description="Valvi offline configuration and local MDB compatibility")
    parser.add_argument("command", choices=["validate-config", "probe-mdb"])
    parser.add_argument("--config", type=Path, default=default_config_path())
    parser.add_argument("--fixture", type=Path, help="Authorized local test MDB copy, optional")
    args = parser.parse_args()
    if args.command == "probe-mdb":
        try:
            result = probe_local(args.fixture)
        except BridgeError as exc:
            print(json.dumps({"status": "BRIDGE_ERROR", "error": str(exc)}))
            return 2
        print(json.dumps(result, indent=2))
        return 0 if result["status"] in ("PROVIDERS_CHECKED", "FIXTURE_READ") else 2
    if args.fixture is not None:
        parser.error("--fixture requires probe-mdb")
    try:
        sources = load_sources(args.config)
    except ConfigError as exc:
        print(json.dumps({"configuration_valid": False, "error": str(exc)}))
        return 2
    print(json.dumps(summary(sources), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
