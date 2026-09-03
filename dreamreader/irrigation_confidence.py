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

def _load_config(project_root: Path) -> dict[str, Any]:
    for path in (project_root/"config"/"config.local.json", project_root/"config"/"config.json"):
        if path.exists():
            try:
                data=_read_json(path)
                if isinstance(data, dict):
                    return data
            except (OSError, json.JSONDecodeError):
                pass
    return {}

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

    config=_load_config(project_root)
    site_timezone=str((config.get("site") or {}).get("timezone") or "UTC")
    operational_cfg=config.get("operationalState") or {}
    max_age_minutes=float(operational_cfg.get("maxEvidenceAgeMinutes") or 10)
    allow_stale_for_testing=bool(operational_cfg.get("allowStaleForTesting", False))

    session=Path(str(state["sourceSession"]))
    snapshot_path=session/"normalized"/"romeo_snapshot.json"
    snapshots=_as_list(_read_json(snapshot_path)) if snapshot_path.exists() else []

    result=[]
    now_utc=datetime.now(timezone.utc)

    for romeo in state.get("romeos", []):
        rid=str(romeo.get("romeoId") or "")
        meters=[x for x in snapshots if str(x.get("RomeoId") or x.get("DreamId") or "")==rid]
        meter_ts=[(_parse_ts(x.get("FlowTimestamp") or x.get("MeterTimestamp"), site_timezone), x) for x in meters]
        meter_ts=[pair for pair in meter_ts if pair[0] is not None]
        latest_flow=max((pair[0] for pair in meter_ts), default=None)

        cycle=romeo.get("cycleEvidence") or {}
        state_name=str(romeo.get("candidateIrrigationState") or "UNKNOWN")
        boundary_raw=cycle.get("cycleStartedAt") if state_name=="IRRIGATING_CANDIDATE" else cycle.get("cycleEndedAt")
        boundary=_parse_ts(boundary_raw, site_timezone)

        latest_program_event=romeo.get("latestProgramEvent") or {}
        program_event_ts=_parse_ts(latest_program_event.get("Timestamp"), site_timezone)

        latest_evidence=max([x for x in (latest_flow, program_event_ts) if x is not None], default=None)
        evidence_age_minutes=None
        if latest_evidence is not None:
            evidence_age_minutes=max(0.0,(now_utc-latest_evidence.astimezone(timezone.utc)).total_seconds()/60.0)
        evidence_fresh=(evidence_age_minutes is not None and evidence_age_minutes <= max_age_minutes)

        nonzero=[x for x in meters if x.get("FlowRawValue") is not None and float(x.get("FlowRawValue") or 0)!=0.0]
        recent_nonzero=[]
        aligned_rows=[]
        if boundary is not None:
            for ts,row in meter_ts:
                if ts >= boundary:
                    aligned_rows.append(row)
                    if row.get("FlowRawValue") is not None and float(row.get("FlowRawValue") or 0)!=0.0:
                        recent_nonzero.append(row)

        flow_support=None
        evidence_basis="UNALIGNED"
        if boundary is not None and meter_ts:
            evidence_basis="AFTER_CYCLE_BOUNDARY"
            if state_name=="IRRIGATING_CANDIDATE":
                flow_support=len(recent_nonzero)>0
            elif state_name=="NOT_IRRIGATING_CANDIDATE":
                # Romeo-level flow is not yet linked to the same program/valve.
                # Therefore it cannot contradict a STOP/FINISH event.
                flow_support=True if len(aligned_rows)>0 and len(recent_nonzero)==0 else None

        if not evidence_fresh and allow_stale_for_testing:
            confidence="TEST_DATA_ACCEPTED"
        elif not evidence_fresh:
            confidence="STALE_EVIDENCE"
        elif flow_support is True:
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
            "latestFlowTimestamp": latest_flow.isoformat() if latest_flow else None,
            "latestProgramEvidenceTimestamp": program_event_ts.isoformat() if program_event_ts else None,
            "latestOperationalEvidenceTimestamp": latest_evidence.isoformat() if latest_evidence else None,
            "operationalEvidenceAgeMinutes": round(evidence_age_minutes,2) if evidence_age_minutes is not None else None,
            "maxEvidenceAgeMinutes": max_age_minutes,
        "allowStaleForTesting": allow_stale_for_testing,
            "evidenceFresh": evidence_fresh,
            "usableForLogicValidation": bool(evidence_fresh or allow_stale_for_testing),
            "testingModeAccepted": bool((not evidence_fresh) and allow_stale_for_testing),
            "flowEvidenceBasis": evidence_basis,
            "flowCorroboratesCandidateState": flow_support,
            "flowScopeValidated": False,
            "confidenceStatus": confidence,
            "canClaimCurrentIrrigation": False,
            "safeNote": "La evidencia antigua puede usarse para validar logica cuando allowStaleForTesting=true, pero nunca se presenta como estado actual de produccion. El flujo crudo no esta aun vinculado a programa/valvula.",
        })

    return {
        "success": True,
        "sourceSession": str(session),
        "siteTimezone": site_timezone,
        "maxEvidenceAgeMinutes": max_age_minutes,
        "romeoCount": len(result),
        "romeos": result,
        "interpretationStatus": "CANDIDATE",
        "safety": {"canClaimCurrentIrrigation": False},
    }
