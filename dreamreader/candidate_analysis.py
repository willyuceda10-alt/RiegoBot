from __future__ import annotations

import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def find_latest_candidate_events(project_root: Path) -> tuple[Path, list[dict[str, Any]]] | None:
    output_root = project_root / "output"
    if not output_root.exists():
        return None

    candidates: list[tuple[float, Path]] = []
    for path in output_root.rglob("operational_events_candidate.json"):
        try:
            candidates.append((path.stat().st_mtime, path))
        except OSError:
            continue

    if not candidates:
        return None

    path = max(candidates, key=lambda item: item[0])[1]
    try:
        raw = _read_json(path)
    except (OSError, json.JSONDecodeError):
        return None

    if isinstance(raw, dict):
        rows = [raw]
    elif isinstance(raw, list):
        rows = [row for row in raw if isinstance(row, dict)]
    else:
        rows = []

    return path, rows


def summarize_candidate_events(project_root: Path) -> dict[str, Any]:
    found = find_latest_candidate_events(project_root)
    if found is None:
        return {
            "success": False,
            "error": "No existe una extraccion candidata de eventos operativos.",
        }

    path, rows = found
    by_romeo: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        by_romeo[str(row.get("RomeoId") or "UNRESOLVED")].append(row)

    romeo_summaries: list[dict[str, Any]] = []
    global_texts = Counter()
    global_codes = Counter()
    fail_values = Counter()

    for romeo_id, items in sorted(by_romeo.items()):
        texts = Counter(str(row.get("ReportTextRaw") or "").strip() or "<VACIO>" for row in items)
        codes = Counter(str(row.get("ReportCodeRaw")) for row in items)
        fails = Counter(str(row.get("ReportFailRaw")) for row in items)
        states = Counter(str(row.get("StateRaw")) for row in items)

        for key, value in texts.items():
            global_texts[key] += value
        for key, value in codes.items():
            global_codes[key] += value
        for key, value in fails.items():
            fail_values[key] += value

        samples = []
        for row in items[:15]:
            samples.append({
                "timestamp": row.get("Timestamp"),
                "reportCodeRaw": row.get("ReportCodeRaw"),
                "reportTextRaw": row.get("ReportTextRaw"),
                "reportFailRaw": row.get("ReportFailRaw"),
                "stateRaw": row.get("StateRaw"),
                "reportId1Raw": row.get("ReportId1Raw"),
                "reportId2Raw": row.get("ReportId2Raw"),
                "reportId2NameRaw": row.get("ReportId2NameRaw"),
            })

        romeo_summaries.append({
            "romeoId": romeo_id,
            "eventCount": len(items),
            "topReportTexts": [{"text": k, "count": v} for k, v in texts.most_common(15)],
            "topReportCodes": [{"code": k, "count": v} for k, v in codes.most_common(15)],
            "reportFailValues": dict(fails),
            "stateValues": dict(states),
            "recentSamples": samples,
        })

    return {
        "success": True,
        "sourceFile": str(path),
        "totalEvents": len(rows),
        "romeoCount": len(by_romeo),
        "globalTopReportTexts": [{"text": k, "count": v} for k, v in global_texts.most_common(25)],
        "globalTopReportCodes": [{"code": k, "count": v} for k, v in global_codes.most_common(25)],
        "globalReportFailValues": dict(fail_values),
        "romeos": romeo_summaries,
        "interpretationStatus": "CANDIDATE",
        "safeNote": "Los codigos, RepFail, State e IDs se muestran como valores crudos. Todavia no se interpretan como alarmas o valvulas activas.",
    }


def build_candidate_operational_state(project_root: Path) -> dict[str, Any]:
    found = find_latest_candidate_events(project_root)
    if found is None:
        return {
            "success": False,
            "error": "No existe una extraccion candidata de eventos operativos.",
        }

    path, rows = found

    def _is_true(value: Any) -> bool:
        if isinstance(value, bool):
            return value
        return str(value).strip().lower() in {"true", "1", "yes"}

    def _timestamp(row: dict[str, Any]) -> str:
        return str(row.get("Timestamp") or "")

    ordered = sorted(rows, key=_timestamp, reverse=True)

    latest_valve_transition: dict[tuple[str, str], dict[str, Any]] = {}
    recent_failures: list[dict[str, Any]] = []
    romeo_ids = sorted({str(row.get("RomeoId") or "UNRESOLVED") for row in rows})

    for row in ordered:
        romeo_id = str(row.get("RomeoId") or "UNRESOLVED")
        code = str(row.get("ReportCodeRaw"))
        valve_name = str(row.get("ReportId2NameRaw") or "").strip()
        valve_id = str(row.get("ReportId2Raw") or "").strip()
        valve_key = valve_name if valve_name not in {"", "0", "None"} else valve_id

        if code in {"29", "30"} and valve_key:
            key = (romeo_id, valve_key)
            if key not in latest_valve_transition:
                latest_valve_transition[key] = {
                    "romeoId": romeo_id,
                    "valveCandidateId": valve_key,
                    "reportId2Raw": row.get("ReportId2Raw"),
                    "reportId2NameRaw": row.get("ReportId2NameRaw"),
                    "latestTransition": "OPEN" if code == "29" else "CLOSED",
                    "timestamp": row.get("Timestamp"),
                    "reportCodeRaw": row.get("ReportCodeRaw"),
                    "reportTextRaw": row.get("ReportTextRaw"),
                    "mappingStatus": "CANDIDATE",
                }

        if _is_true(row.get("ReportFailRaw")):
            recent_failures.append({
                "romeoId": romeo_id,
                "timestamp": row.get("Timestamp"),
                "reportCodeRaw": row.get("ReportCodeRaw"),
                "reportTextRaw": row.get("ReportTextRaw"),
                "reportId1Raw": row.get("ReportId1Raw"),
                "reportId2Raw": row.get("ReportId2Raw"),
                "reportId2NameRaw": row.get("ReportId2NameRaw"),
                "mappingStatus": "CANDIDATE",
            })

    valves = sorted(
        latest_valve_transition.values(),
        key=lambda item: (item["romeoId"], item["valveCandidateId"]),
    )

    open_transitions = [item for item in valves if item["latestTransition"] == "OPEN"]
    closed_transitions = [item for item in valves if item["latestTransition"] == "CLOSED"]

    return {
        "success": True,
        "sourceFile": str(path),
        "romeosObserved": romeo_ids,
        "latestValveTransitions": valves,
        "latestOpenTransitionCount": len(open_transitions),
        "latestClosedTransitionCount": len(closed_transitions),
        "recentFailureEventCount": len(recent_failures),
        "recentFailureEvents": recent_failures[:30],
        "interpretationStatus": "CANDIDATE",
        "safety": {
            "canClaimCurrentValveState": False,
            "canClaimActiveAlarm": False,
            "reason": (
                "Las transiciones 29/30 y RepFail muestran patrones consistentes, "
                "pero aun no se ha validado que representen estado actual completo ni ciclo de alarma activa/resuelta."
            ),
        },
    }
