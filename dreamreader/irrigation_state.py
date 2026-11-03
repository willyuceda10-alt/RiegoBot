from __future__ import annotations

import csv
import json
from datetime import datetime
from pathlib import Path
from typing import Any

START_CODES={"19","15"}
STOP_CODES={"16","31"}
OPEN_CODE="29"
CLOSE_CODE="30"

def _read_csv(path: Path) -> list[dict[str,str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))

def _parse_timestamp(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None

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
            events.sort(key=lambda e: _parse_timestamp(e.get("Timestamp")) or datetime.min, reverse=True)

            latest_program_event=None
            for e in events:
                code=str(e.get("ReportCodeRaw") or "")
                if code in START_CODES|STOP_CODES:
                    latest_program_event=e
                    break

            candidate_program_state=None
            cycle_start=None
            program_candidate_id=None
            if latest_program_event:
                code=str(latest_program_event.get("ReportCodeRaw") or "")
                candidate_program_state="STARTED" if code in START_CODES else "STOPPED_OR_FINISHED"
                cycle_start=_parse_timestamp(latest_program_event.get("Timestamp"))
                program_candidate_id=str(latest_program_event.get("ReportId1Raw") or "")

            cycle_events=[]
            if candidate_program_state=="STARTED" and cycle_start is not None:
                for e in events:
                    ts=_parse_timestamp(e.get("Timestamp"))
                    if ts is None or ts < cycle_start:
                        continue
                    if program_candidate_id and str(e.get("ReportId1Raw") or "") not in {"", program_candidate_id}:
                        continue
                    cycle_events.append(e)

            latest_valve={}
            for e in cycle_events:
                code=str(e.get("ReportCodeRaw") or "")
                if code not in {OPEN_CODE,CLOSE_CODE}:
                    continue
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

            active_valves=[x for x in valve_states if x["latestTransition"]=="OPEN"]
            cycle_evidence={
                "programCandidateId": program_candidate_id or None,
                "cycleStartedAt": latest_program_event.get("Timestamp") if candidate_program_state=="STARTED" else None,
                "cycleEndedAt": latest_program_event.get("Timestamp") if candidate_program_state=="STOPPED_OR_FINISHED" else None,
                "eventsInCurrentCycle": len(cycle_events),
                "activeValveCandidates": active_valves,
            }

            if candidate_program_state=="STOPPED_OR_FINISHED":
                candidate_irrigation_state="NOT_IRRIGATING_CANDIDATE"
                confidence_reason="El ultimo evento de programa observado es parada/fin; las aperturas anteriores quedan fuera del ciclo vigente."
            elif candidate_program_state=="STARTED" and active_valves:
                candidate_irrigation_state="IRRIGATING_CANDIDATE"
                confidence_reason="El ultimo evento de programa es inicio y existe al menos una valvula cuya ultima transicion dentro de ese mismo ciclo es OPEN."
            elif candidate_program_state=="STARTED":
                candidate_irrigation_state="STARTED_WITHOUT_OPEN_VALVE_EVIDENCE"
                confidence_reason="El ultimo evento de programa es inicio, pero no hay una valvula con ultima transicion OPEN dentro del ciclo observado."
            else:
                candidate_irrigation_state="UNKNOWN"
                confidence_reason="No se encontro un evento reciente de inicio/fin de programa en la muestra."

            romeos.append({
                "romeoId":rid,
                "sourceTable":src.get("SourceTable"),
                "sampleCount":src.get("SampleCount"),
                "latestProgramEvent":latest_program_event,
                "candidateProgramState":candidate_program_state,
                "candidateIrrigationState":candidate_irrigation_state,
                "cycleEvidence":cycle_evidence,
                "latestValveTransitionsInCurrentCycle":valve_states,
                "openTransitionCountInCurrentCycle":len(active_valves),
                "closedTransitionCountInCurrentCycle":sum(1 for x in valve_states if x["latestTransition"]=="CLOSED"),
                "canClaimCurrentIrrigation":False,
                "reason":confidence_reason + " Aun falta validar la semantica contra el estado visible en Dream antes de habilitar una afirmacion productiva.",
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
