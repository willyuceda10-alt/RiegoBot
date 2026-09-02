from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
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


def _parse_timestamp(value: Any, site_timezone: str = "UTC") -> datetime | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        try:
            parsed = parsed.replace(tzinfo=ZoneInfo(site_timezone))
        except ZoneInfoNotFoundError:
            parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


def build_romeo_summary(
    project_root: Path,
    romeo_id: str,
    stale_after_hours: float = 24.0,
    site_timezone: str = "UTC",
) -> dict[str, Any]:
    payload = build_romeo_query(project_root, romeo_id)
    if not payload.get("success"):
        return payload

    meters = list(payload.get("meters") or [])
    timestamps = [
        ts for ts in (
            _parse_timestamp(row.get("FlowTimestamp") or row.get("MeterTimestamp"), site_timezone)
            for row in meters
        )
        if ts is not None
    ]
    latest = max(timestamps) if timestamps else None
    now = datetime.now(timezone.utc)
    age_hours = None
    is_stale = True
    if latest is not None:
        age_hours = max(0.0, (now - latest.astimezone(timezone.utc)).total_seconds() / 3600.0)
        is_stale = age_hours > stale_after_hours

    nonzero = [
        row for row in meters
        if row.get("FlowRawValue") is not None and float(row.get("FlowRawValue") or 0) != 0.0
    ]

    return {
        "success": True,
        "romeoId": payload.get("romeoId"),
        "romeoKey": payload.get("romeoKey"),
        "sessionId": payload.get("sessionId"),
        "sessionEndTime": payload.get("sessionEndTime"),
        "siteTimezone": site_timezone,
        "latestDataTimestamp": latest.isoformat() if latest else None,
        "dataAgeHours": round(age_hours, 2) if age_hours is not None else None,
        "freshnessStatus": "STALE" if is_stale else "FRESH",
        "staleAfterHours": stale_after_hours,
        "meterCount": len(meters),
        "nonZeroFlowObservationCount": len(nonzero),
        "nonZeroFlowObservations": nonzero,
        "accumulationSummary": payload.get("accumulationSummary"),
        "candidateStatusObservation": payload.get("candidateStatusObservation"),
        "safeInterpretation": {
            "canClaimCurrentIrrigation": False,
            "reason": (
                "Los valores de flujo siguen sin unidad/semantica confirmada y la frescura debe validarse."
                if not is_stale
                else "La ultima lectura disponible supera el umbral de frescura configurado."
            ),
            "flowUnitStatus": "UNRESOLVED",
            "accumulationUnitStatus": payload.get("dataSemantics", {}).get("accumulationUnitStatus"),
        },
    }


def build_operator_message(project_root: Path, romeo_id: str, site_timezone: str = "UTC") -> dict[str, Any]:
    summary = build_romeo_summary(project_root, romeo_id, site_timezone=site_timezone)
    if not summary.get("success"):
        return summary

    freshness = summary.get("freshnessStatus")
    latest = summary.get("latestDataTimestamp")
    meter_count = int(summary.get("meterCount") or 0)
    nonzero_count = int(summary.get("nonZeroFlowObservationCount") or 0)
    age_hours = summary.get("dataAgeHours")

    if freshness == "STALE":
        message = (
            f"Romeo {romeo_id}: la ultima lectura disponible es de {latest}. "
            f"Tiene aproximadamente {age_hours} horas de antiguedad, por lo que no puedo confirmar el riego actual. "
            f"Se encontraron {meter_count} medidores y {nonzero_count} lecturas de flujo crudo distintas de cero."
        )
    else:
        message = (
            f"Romeo {romeo_id}: la ultima lectura disponible es de {latest}. "
            f"Se encontraron {meter_count} medidores y {nonzero_count} lecturas de flujo crudo distintas de cero. "
            "Aun no puedo afirmar el caudal ni el riego actual porque las unidades y la semantica del flujo siguen sin confirmar."
        )

    return {
        "success": True,
        "romeoId": str(romeo_id),
        "freshnessStatus": freshness,
        "message": message,
        "details": {
            "latestDataTimestamp": latest,
            "dataAgeHours": age_hours,
            "meterCount": meter_count,
            "nonZeroFlowObservationCount": nonzero_count,
            "flowUnitStatus": "UNRESOLVED",
            "canClaimCurrentIrrigation": False,
        },
    }


def parse_operator_question(text: str) -> dict[str, Any]:
    normalized = " ".join(str(text or "").strip().split())
    if not normalized:
        return {"success": False, "error": "La pregunta esta vacia."}

    match = re.search(r"\b(?:romeo|dream|controlador)\s*[-:#]?\s*(\d+)\b", normalized, flags=re.IGNORECASE)
    if match is None:
        if normalized.isdigit():
            return {"success": True, "romeoId": normalized, "intent": "romeo_status"}
        return {
            "success": False,
            "error": "No pude identificar el numero de Romeo. Ejemplo: que pasa con el Romeo 11",
        }

    lower = normalized.lower()
    if any(word in lower for word in ("caudal", "flujo")):
        intent = "flow_status"
    elif any(word in lower for word in ("riega", "regando", "riego")):
        intent = "irrigation_status"
    elif any(word in lower for word in ("alarma", "alerta")):
        intent = "alarm_status"
    else:
        intent = "romeo_status"

    return {
        "success": True,
        "romeoId": match.group(1),
        "intent": intent,
        "originalQuestion": normalized,
    }


def answer_operator_question(project_root: Path, text: str, site_timezone: str = "UTC") -> dict[str, Any]:
    parsed = parse_operator_question(text)
    if not parsed.get("success"):
        return parsed

    romeo_id = str(parsed["romeoId"])
    intent = str(parsed.get("intent") or "romeo_status")
    summary = build_romeo_summary(project_root, romeo_id, site_timezone=site_timezone)
    if not summary.get("success"):
        return summary

    latest = summary.get("latestDataTimestamp")
    age_hours = summary.get("dataAgeHours")
    freshness = summary.get("freshnessStatus")
    meter_count = int(summary.get("meterCount") or 0)
    nonzero_count = int(summary.get("nonZeroFlowObservationCount") or 0)
    candidate_status = summary.get("candidateStatusObservation")

    if intent == "alarm_status":
        message = (
            f"Romeo {romeo_id}: todavia no tengo una fuente de alarmas validada para confirmar si existe una alarma activa. "
            "No voy a inferir una alarma a partir del flujo ni de otros datos."
        )
        if candidate_status is not None:
            message += " Existe una observacion candidata de estado, pero no esta validada como alarma."
        details = {
            "alarmSourceStatus": "UNRESOLVED",
            "alarmConfirmed": None,
            "candidateStatusAvailable": candidate_status is not None,
            "latestDataTimestamp": latest,
            "freshnessStatus": freshness,
        }
    elif intent == "flow_status":
        if freshness == "STALE":
            message = (
                f"Romeo {romeo_id}: la ultima lectura de flujo disponible es de {latest} "
                f"y tiene aproximadamente {age_hours} horas de antiguedad. "
                f"Hay {nonzero_count} lecturas de flujo crudo distintas de cero entre {meter_count} medidores. "
                "Las unidades del flujo aun no estan confirmadas."
            )
        else:
            message = (
                f"Romeo {romeo_id}: hay {nonzero_count} lecturas de flujo crudo distintas de cero "
                f"entre {meter_count} medidores. Las unidades del flujo aun no estan confirmadas."
            )
        details = {
            "latestDataTimestamp": latest,
            "dataAgeHours": age_hours,
            "freshnessStatus": freshness,
            "meterCount": meter_count,
            "nonZeroFlowObservationCount": nonzero_count,
            "flowUnitStatus": "UNRESOLVED",
        }
    elif intent == "irrigation_status":
        if freshness == "STALE":
            message = (
                f"Romeo {romeo_id}: no puedo confirmar si esta regando ahora. "
                f"La ultima lectura disponible es de {latest} y tiene aproximadamente {age_hours} horas de antiguedad."
            )
        else:
            message = (
                f"Romeo {romeo_id}: los datos son recientes, pero todavia no puedo confirmar que este regando "
                "porque la semantica y las unidades del flujo no estan validadas."
            )
        details = {
            "latestDataTimestamp": latest,
            "dataAgeHours": age_hours,
            "freshnessStatus": freshness,
            "canClaimCurrentIrrigation": False,
        }
    else:
        response = build_operator_message(project_root, romeo_id, site_timezone=site_timezone)
        message = response.get("message")
        details = response.get("details")

    return {
        "success": True,
        "intent": intent,
        "romeoId": romeo_id,
        "question": parsed.get("originalQuestion", text),
        "message": message,
        "details": details,
    }
