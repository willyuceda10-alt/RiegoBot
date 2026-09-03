from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any

START_CODES={"19","15"}
STOP_CODES={"16","31"}
OPEN_CODE="29"
CLOSE_CODE="30"

def _read_csv(path: Path) -> list[dict[str,str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))

def build_irrigation_state_candidate(project_root: Path) -> dict[str, Any]:
    output_root=project_root/"output"
    sessions=sorted([p for p in output_root.rglob("normalized") if p.is_dir()], key=lambda p:p.stat().st_mtime, reverse=True)
    for normalized in sessions:
        source_file=normalized/"irrigation_state_sources_candidate.json"
        if not source_file.exists():
            continue
        raw=json.loads(source_file.read_text(encoding="utf-8-sig"))
        sources=[raw] if isinstance(raw,dict) else raw if isinstance(raw,list) else []
        romeos=[]
        for src in sources:
            rid=str(src.get("RomeoId") or "")
            events_file=normalized/f"irrigation_state_events_{rid}.csv"
            if not events_file.exists():
                continue
            events=_read_csv(events_file)
            latest_program_event=None
            latest_valve={}
            for e in events:
                code=str(e.get("ReportCodeRaw") or "")
                if latest_program_event is None and code in START_CODES|STOP_CODES:
                    latest_program_event=e
                if code in {OPEN_CODE,CLOSE_CODE}:
                    valve=str(e.get("ReportId2NameRaw") or e.get("ReportId2Raw") or "")
                    if valve and valve not in latest_valve:
                        latest_valve[valve]=e
            valve_states=[]
            for valve,e in latest_valve.items():
                code=str(e.get("ReportCodeRaw") or "")
                valve_states.append({
                    "valveCandidateId": valve,
                    "latestTransition": "OPEN" if code==OPEN_CODE else "CLOSED",
                    "timestamp": e.get("Timestamp"),
                    "reportId1Raw": e.get("ReportId1Raw"),
                    "reportId2Raw": e.get("ReportId2Raw"),
                    "sourceTable": e.get("SourceTable"),
                })
            candidate_program_state=None
            if latest_program_event:
                code=str(latest_program_event.get("ReportCodeRaw") or "")
                candidate_program_state="STARTED" if code in START_CODES else "STOPPED_OR_FINISHED"
            romeos.append({
                "romeoId":rid,
                "sourceTable":src.get("SourceTable"),
                "sampleCount":src.get("SampleCount"),
                "latestProgramEvent":latest_program_event,
                "candidateProgramState":candidate_program_state,
                "latestValveTransitions":valve_states,
                "openTransitionCount":sum(1 for x in valve_states if x["latestTransition"]=="OPEN"),
                "closedTransitionCount":sum(1 for x in valve_states if x["latestTransition"]=="CLOSED"),
                "canClaimCurrentIrrigation":False,
                "reason":"Se reconstruye la ultima secuencia observada, pero aun falta validar completitud temporal y semantica de programa activo para afirmar REGANDO/DETENIDO.",
            })
        return {
            "success":True,
            "sourceSession":str(normalized.parent),
            "romeoCount":len(romeos),
            "romeos":romeos,
            "interpretationStatus":"CANDIDATE",
            "safety":{"canClaimCurrentIrrigation":False},
        }
    return {"success":False,"error":"No existe una sesion con investigacion candidata de estado de riego."}
