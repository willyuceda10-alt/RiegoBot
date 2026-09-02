from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _as_list(value: Any) -> list[dict[str, Any]]:
    if value is None:
        return []
    if isinstance(value, list):
        return [item for item in value if isinstance(item, dict)]
    if isinstance(value, dict):
        return [value]
    return []


def find_latest_valid_session(project_root: Path) -> Path | None:
    output_root = project_root / "output"
    if not output_root.exists():
        return None

    candidates: list[tuple[float, Path]] = []
    for session_file in output_root.rglob("session.json"):
        try:
            summary = _read_json(session_file)
        except (OSError, json.JSONDecodeError):
            continue
        if summary.get("Errors"):
            continue
        if int(summary.get("DreamsDiscovered") or 0) <= 0:
            continue
        candidates.append((session_file.stat().st_mtime, session_file.parent))

    if not candidates:
        return None
    return max(candidates, key=lambda item: item[0])[1]


def build_romeo_query(project_root: Path, romeo_id: str) -> dict[str, Any]:
    session_dir = find_latest_valid_session(project_root)
    if session_dir is None:
        return {
            "success": False,
            "romeoId": str(romeo_id),
            "error": "No existe una sesion valida de DreamReader.",
        }

    session_summary = _read_json(session_dir / "session.json")
    normalized_dir = session_dir / "normalized"
    snapshot_path = normalized_dir / "romeo_snapshot.json"
    accumulation_path = normalized_dir / "accumulation_summary.json"
    dream_status_path = normalized_dir / "dream_status.json"

    snapshots = _as_list(_read_json(snapshot_path)) if snapshot_path.exists() else []
    meters = [row for row in snapshots if str(row.get("RomeoId") or row.get("DreamId") or "") == str(romeo_id)]

    accumulation_rows = _as_list(_read_json(accumulation_path)) if accumulation_path.exists() else []
    accumulation = next(
        (row for row in accumulation_rows if str(row.get("RomeoId") or row.get("DreamId") or "") == str(romeo_id)),
        None,
    )

    status_rows = _as_list(_read_json(dream_status_path)) if dream_status_path.exists() else []
    status = next(
        (row for row in status_rows if str(row.get("DreamId") or "") == str(romeo_id)),
        None,
    )

    if not meters and accumulation is None and status is None:
        return {
            "success": False,
            "romeoId": str(romeo_id),
            "sessionId": session_summary.get("SessionId"),
            "error": f"No hay datos normalizados para Romeo {romeo_id}.",
        }

    return {
        "success": True,
        "romeoId": str(romeo_id),
        "romeoKey": meters[0].get("RomeoKey") if meters else None,
        "sessionId": session_summary.get("SessionId"),
        "sessionEndTime": session_summary.get("EndTime"),
        "meterCount": len(meters),
        "meters": meters,
        "accumulationSummary": accumulation,
        "candidateStatusObservation": status,
        "dataSemantics": {
            "flowUnitStatus": "UNRESOLVED",
            "accumulationUnitStatus": "UNRESOLVED" if accumulation else None,
            "candidateStatus": status is not None,
        },
    }
