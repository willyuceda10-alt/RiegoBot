from __future__ import annotations

import json
import os
import shutil
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .bridge import invoke_readonly_bridge
from .config import load_config
from .discovery import discover_dreams, get_discovery_info


def _runtime_dir(project_root: Path) -> Path:
    path = project_root / "runtime"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _write_status(project_root: Path, payload: dict[str, Any]) -> None:
    runtime_dir = _runtime_dir(project_root)
    temp = runtime_dir / "collector_status.json.tmp"
    final = runtime_dir / "collector_status.json"
    temp.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    temp.replace(final)


def _pid_is_running(pid: int) -> bool:
    if pid <= 0:
        return False
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    return True


def _acquire_lock(project_root: Path) -> Path | None:
    lock_path = _runtime_dir(project_root) / "collector.lock"
    if lock_path.exists():
        try:
            existing_pid = int(lock_path.read_text(encoding="utf-8").strip())
        except (OSError, ValueError):
            existing_pid = -1
        if _pid_is_running(existing_pid):
            return None
        try:
            lock_path.unlink()
        except OSError:
            return None

    try:
        lock_path.write_text(str(os.getpid()), encoding="utf-8")
    except OSError:
        return None
    return lock_path


def _prune_sessions(project_root: Path, config: dict[str, Any], keep: int, protected: Path | None) -> int:
    site_id = str(config.get("collector", {}).get("siteId", ""))
    collector_id = str(config.get("collector", {}).get("collectorId", ""))
    root = project_root / "output" / site_id / collector_id
    if not root.exists():
        return 0

    sessions = [
        path for path in root.iterdir()
        if path.is_dir() and (path / "session.json").exists()
    ]
    sessions.sort(key=lambda path: path.stat().st_mtime, reverse=True)

    removed = 0
    protected_resolved = protected.resolve() if protected and protected.exists() else None
    for session_dir in sessions[max(1, keep):]:
        try:
            if protected_resolved is not None and session_dir.resolve() == protected_resolved:
                continue
            shutil.rmtree(session_dir)
            removed += 1
        except OSError:
            continue
    return removed


def run_realtime_collector(project_root: Path) -> int:
    config = load_config(project_root)
    realtime = config.get("realtime", {})
    interval_seconds = max(10, int(realtime.get("pollIntervalSeconds", 30)))
    allow_candidates = bool(realtime.get("allowCandidateMappings", False))
    max_failures = max(1, int(realtime.get("maxConsecutiveFailures", 10)))
    retention_sessions = max(10, int(realtime.get("retentionSessions", 120)))

    lock_path = _acquire_lock(project_root)
    if lock_path is None:
        _write_status(project_root, {
            "running": False,
            "success": False,
            "timestampUtc": datetime.now(timezone.utc).isoformat(),
            "error": "Ya existe otro collector realtime activo.",
            "exitCode": 8,
        })
        return 8

    failures = 0
    cycle = 0

    try:
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
                    "retentionSessions": retention_sessions,
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

                latest = Path(bridge.latest_session) if bridge.latest_session else None
                removed = _prune_sessions(project_root, config, retention_sessions, latest)

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
                    "retentionSessions": retention_sessions,
                    "sessionsPrunedThisCycle": removed,
                    "collectorPid": os.getpid(),
                })

            if failures >= max_failures:
                _write_status(project_root, {
                    "running": False,
                    "cycle": cycle,
                    "success": False,
                    "timestampUtc": datetime.now(timezone.utc).isoformat(),
                    "error": "Collector detenido por fallos consecutivos.",
                    "consecutiveFailures": failures,
                    "exitCode": 9,
                })
                return 9

            time.sleep(interval_seconds)
    finally:
        try:
            if lock_path.exists():
                lock_path.unlink()
        except OSError:
            pass
