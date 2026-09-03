from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .irrigation_state import build_irrigation_state_candidate

def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8-sig"))

def _as_list(value: Any) -> list[dict[str, Any]]:
    if isinstance(value, list):
        return [x for x in value if isinstance(x, dict)]
    if isinstance(value, dict):
        return [value]
    return []

def _parse_ts(value: Any) -> datetime | None:
    if not value:
        return None
    text=str(value).replace("Z","+00:00")
    try:
        dt=datetime.fromisoformat(text)
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt=dt.replace(tzinfo=timezone.utc)
    return dt

def build_irrigation_confidence_candidate(project_root: Path) -> dict[str, Any]:
    state=build_irrigation_state_candidate(project_root)
    if not state.get("success"):
        return state

    session=Path(str(state["sourceSession"]))
    snapshot_path=session/"normalized"/"romeo_snapshot.json"
    snapshots=_as_list(_read_json(snapshot_path)) if snapshot_path.exists() else []

    result=[]
    for romeo in state.get("romeos", []):
        rid=str(romeo.get("romeoId") or "")
        meters=[x for x in snapshots if str(x.get("RomeoId") or x.get("DreamId") or "")==rid]
        nonzero=[x for x in meters if x.get("FlowRawValue") is not None and float(x.get("FlowRawValue") or 0)!=0.0]
        ts=[_parse_ts(x.get("FlowTimestamp") or x.get("MeterTimestamp")) for x in meters]
        ts=[x for x in ts if x is not None]
        latest=max(ts) if ts else None
        age_hours=None
        if latest is not None:
            age_hours=max(0.0,(datetime.now(timezone.utc)-latest.astimezone(timezone.utc)).total_seconds()/3600.0)

        state_name=str(romeo.get("candidateIrrigationState") or "UNKNOWN")
        flow_support=None
        if state_name=="IRRIGATING_CANDIDATE":
            flow_support=len(nonzero)>0
        elif state_name=="NOT_IRRIGATING_CANDIDATE":
            flow_support=len(nonzero)==0

        if flow_support is True:
            confidence="CORROBORATED_CANDIDATE"
        elif flow_support is False:
            confidence="CONFLICTING_EVIDENCE"
        else:
            confidence="UNRESOLVED"

        result.append({
            "romeoId": rid,
            "candidateIrrigationState": state_name,
            "programCandidateState": romeo.get("candidateProgramState"),
            "programCandidateId": (romeo.get("cycleEvidence") or {}).get("programCandidateId"),
            "activeValveCandidates": (romeo.get("cycleEvidence") or {}).get("activeValveCandidates", []),
            "meterCount": len(meters),
            "nonZeroFlowObservationCount": len(nonzero),
            "latestFlowTimestamp": latest.isoformat() if latest else None,
            "flowAgeHours": round(age_hours,2) if age_hours is not None else None,
            "flowCorroboratesCandidateState": flow_support,
            "confidenceStatus": confidence,
            "canClaimCurrentIrrigation": False,
            "safeNote": "El flujo solo se usa como corroboracion binaria cruda; sus unidades y semantica siguen sin validar. No habilita aun una afirmacion productiva.",
        })

    return {
        "success": True,
        "sourceSession": str(session),
        "romeoCount": len(result),
        "romeos": result,
        "interpretationStatus": "CANDIDATE",
        "safety": {"canClaimCurrentIrrigation": False},
    }
