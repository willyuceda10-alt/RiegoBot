from __future__ import annotations

import json
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .bridge import invoke_readonly_bridge
from .config import load_config
from .discovery import discover_dreams, get_discovery_info


def _write_status(project_root: Path, payload: dict[str, Any]) -> None:
    runtime_dir = project_root / "runtime"
    runtime_dir.mkdir(parents=True, exist_ok=True)
    temp = runtime_dir / "collector_status.json.tmp"
    final = runtime_dir / "collector_status.json"
    temp.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    temp.replace(final)


def run_realtime_collector(project_root: Path) -> int:
    config = load_config(project_root)
    realtime = config.get("realtime", {})
    interval_seconds = max(10, int(realtime.get("pollIntervalSeconds", 30)))
    allow_candidates = bool(realtime.get("allowCandidateMappings", False))
    max_failures = max(1, int(realtime.get("maxConsecutiveFailures", 10)))

    failures = 0
    cycle = 0

    while True:
        cycle += 1
        started = datetime.now(timezone.utc)
        discovery_info = get_discovery_info(project_root, config)
        dreams = discover_dreams(project_root, config)

        if not dreams:
            failures += 1
            _write_status(project_root, {
                "running": True,
                "cycle": cycle,
                "success": False,
                "timestampUtc": started.isoformat(),
                "error": "No se encontraron controladores Dream.",
                "consecutiveFailures": failures,
            })
        else:
            bridge = invoke_readonly_bridge(
                project_root,
                "NORMALIZED",
                Path(discovery_info["rootPath"]),
                allow_candidate_mappings=allow_candidates,
            )
            if bridge.success:
                failures = 0
            else:
                failures += 1

            _write_status(project_root, {
                "running": True,
                "cycle": cycle,
                "success": bridge.success,
                "timestampUtc": started.isoformat(),
                "intervalSeconds": interval_seconds,
                "candidateMappingsEnabled": allow_candidates,
                "latestSession": bridge.latest_session,
                "sessionSummary": bridge.session_summary,
                "consecutiveFailures": failures,
                "exitCode": bridge.exit_code,
            })

        if failures >= max_failures:
            _write_status(project_root, {
                "running": False,
                "cycle": cycle,
                "success": False,
                "timestampUtc": datetime.now(timezone.utc).isoformat(),
                "error": "Collector detenido por fallos consecutivos.",
                "consecutiveFailures": failures,
            })
            return 9

        time.sleep(interval_seconds)
