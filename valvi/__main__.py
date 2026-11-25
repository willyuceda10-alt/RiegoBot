import argparse
import json
from pathlib import Path

from .sources import ConfigError, default_config_path, load_sources, summary


def main() -> int:
    parser = argparse.ArgumentParser(description="Valvi offline configuration validation")
    parser.add_argument("command", choices=["validate-config"])
    parser.add_argument("--config", type=Path, default=default_config_path())
    args = parser.parse_args()
    try:
        sources = load_sources(args.config)
    except ConfigError as exc:
        print(json.dumps({"configuration_valid": False, "error": str(exc)}))
        return 2
    print(json.dumps(summary(sources), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
