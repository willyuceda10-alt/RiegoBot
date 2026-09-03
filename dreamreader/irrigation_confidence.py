from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from .irrigation_state import build_irrigation_state_candidate

def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8-sig"))

def _as_list(value: Any) -> list[dict[str, Any]]:
    if isinstance(value, list):
        return [x for x in value if isinstance(x, dict)]
    if isinstance(value, dict):
        return [value]
    return []

def _load_site_timezone(project_root: Path) -> str:
    for path in (project_root/"config"/"config.local.json", project_root/"config"/"config.json"):
        if path.exists():
            try:
                data=_read_json(path)
                return str((data.get("site") or {}).get("timezone") or "UTC")
            except (OSError, json.JSONDecodeError):
                pass
    return "UTC"

def _parse_ts(value: Any, site_timezone: str) -> datetime | None:
    if not value:
        return None
    text=str(value).strip().replace("Z","+00:00")
    try:
        dt=datetime.fromisoformat(text)
    except ValueError:
        return None
    if dt.tzinfo is None:
        try:
            dt=dt.replace(tzinfo=ZoneInfo(site_timezone))
        except ZoneInfoNotFoundError:
            dt=dt.replace(tzinfo=timezone.utc)
    return dt

def build_irrigation_confidence_candidate(project_root: Path) -> dict[str, Any]:
    state=build_irrigation_state_candidate(project_root)
    if not state.get("success"):
        return state

    site_timezone=_load_site_timezone(project_root)
    session=Path(str(state["sourceSession"]))
    snapshot_path=session/"normalized"/"romeo_snapshot.json"
    snapshots=_as_list(_read_json(snapshot_path)) if snapshot_path.exists() else []

    result=[]
    for romeo in state.get("romeos", []):
        rid=str(romeo.get("romeoId") or "")
        meters=[x for x in snapshots if str(x.get("RomeoId") or x.get("DreamId") or "")==rid]
        nonzero=[x for x in meters if x.get("FlowRawValue") is not None and float(x.get("FlowRawValue") or 0)!=0.0]
        meter_ts=[(_parse_ts(x.get("FlowTimestamp") or x.get("MeterTimestamp"), site_timezone), x) for x in meters]
        meter_ts=[pair for pair in meter_ts if pair[0] is not None]
        latest=max((pair[0] for pair in meter_ts), default=None)

        age_hours=None
        if latest is not None:
            age_hours=max(0.0,(datetime.now(timezone.utc)-latest.astimezone(timezone.utc)).total_seconds()/3600.0)

        cycle=romeo.get("cycleEvidence") or {}
        state_name=str(romeo.get("candidateIrrigationState") or "UNKNOWN")
        boundary_raw=cycle.get("cycleStartedAt") if state_name=="IRRIGATING_CANDIDATE" else cycle.get("cycleEndedAt")
        boundary=_parse_ts(boundary_raw, site_timezone)

        recent_nonzero=[]
        recent_zero=[]
        if boundary is not None:
            for ts,row in meter_ts:
                if ts >= boundary:
                    if row.get("FlowRawValue") is not None and float(row.get("FlowRawValue") or 0)!=0.0:
                        recent_nonzero.append(row)
                    else:
                        recent_zero.append(row)

        flow_support=None
        evidence_basis="UNALIGNED"
        if boundary is not None and meter_ts:
            evidence_basis="AFTER_CYCLE_BOUNDARY"
            if state_name=="IRRIGATING_CANDIDATE":
                flow_support=len(recent_nonzero)>0
            elif state_name=="NOT_IRRIGATING_CANDIDATE":
                # Do not treat older/non-aligned non-zero snapshots as a conflict.
                flow_support=(len(recent_nonzero)==0) if any(ts >= boundary for ts,_ in meter_ts) else None

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
            "programCandidateId": cycle.get("programCandidateId"),
            "cycleBoundaryTimestamp": boundary.isoformat() if boundary else None,
            "activeValveCandidates": cycle.get("activeValveCandidates", []),
            "meterCount": len(meters),
            "nonZeroFlowObservationCount": len(nonzero),
            "nonZeroFlowAfterCycleBoundaryCount": len(recent_nonzero),
            "latestFlowTimestamp": latest.isoformat() if latest else None,
            "flowAgeHours": round(age_hours,2) if age_hours is not None else None,
            "flowEvidenceBasis": evidence_basis,
            "flowCorroboratesCandidateState": flow_support,
            "confidenceStatus": confidence,
            "canClaimCurrentIrrigation": False,
            "safeNote": "La corroboracion usa solo flujo crudo temporalmente alineado al ciclo y la zona horaria del sitio. Las unidades/semantica siguen sin validar, por lo que no habilita aun una afirmacion productiva.",
        })

    return {
        "success": True,
        "sourceSession": str(session),
        "siteTimezone": site_timezone,
        "romeoCount": len(result),
        "romeos": result,
        "interpretationStatus": "CANDIDATE",
        "safety": {"canClaimCurrentIrrigation": False},
    }
