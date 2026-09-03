from __future__ import annotations

import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any

DEFAULT_RULES: dict[str, dict[str, Any]] = {
    "33": {"type": "HIGH_FLOW", "severity": "HIGH", "slaMinutes": 10, "reminderEveryMinutes": 10, "escalateAfterMinutes": 30, "coordinatorEscalateAfterMinutes": 45},
    "34": {"type": "LOW_FLOW", "severity": "HIGH", "slaMinutes": 10, "reminderEveryMinutes": 10, "escalateAfterMinutes": 30, "coordinatorEscalateAfterMinutes": 45},
    "2": {"type": "RTU_COMMUNICATION_ERROR", "severity": "CRITICAL", "slaMinutes": 5, "reminderEveryMinutes": 5, "escalateAfterMinutes": 15, "coordinatorEscalateAfterMinutes": 30},
    "50": {"type": "NO_FERTIGATION_FLOW", "severity": "HIGH", "slaMinutes": 10, "reminderEveryMinutes": 10, "escalateAfterMinutes": 30, "coordinatorEscalateAfterMinutes": 45},
    "43": {"type": "LOCAL_LEAK_EVENT", "severity": "MEDIUM", "slaMinutes": 15, "reminderEveryMinutes": 15, "escalateAfterMinutes": 45, "coordinatorEscalateAfterMinutes": 60},
}

def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8-sig"))

def _latest_reports_file(project_root: Path) -> Path | None:
    root = project_root / "output"
    candidates: list[tuple[float, Path]] = []
    if root.exists():
        for path in root.rglob("reports_history_candidate.json"):
            try:
                candidates.append((path.stat().st_mtime, path))
            except OSError:
                continue
    return max(candidates, key=lambda item: item[0])[1] if candidates else None

def _incident_id(row: dict[str, Any]) -> str:
    raw = "|".join([
        str(row.get("RomeoId") or ""),
        str(row.get("Timestamp") or ""),
        str(row.get("ReportCodeRaw") or ""),
        str(row.get("ReportId1Raw") or ""),
        str(row.get("ReportId2Raw") or ""),
        str(row.get("ReportId2NameRaw") or ""),
    ])
    return "INC-" + hashlib.sha1(raw.encode("utf-8")).hexdigest()[:12].upper()

def build_incident_candidates(project_root: Path) -> dict[str, Any]:
    source = _latest_reports_file(project_root)
    if source is None:
        return {"success": False, "error": "No existe reports_history_candidate.json."}

    raw = _read_json(source)
    rows = [raw] if isinstance(raw, dict) else [row for row in raw if isinstance(row, dict)] if isinstance(raw, list) else []
    incidents: list[dict[str, Any]] = []

    for row in rows:
        code = str(row.get("ReportCodeRaw") or "")
        fail = str(row.get("ReportFailRaw") or "").lower() in {"true", "1"}
        rule = DEFAULT_RULES.get(code)
        if rule is None and not fail:
            continue

        rule = rule or {
            "type": "UNCLASSIFIED_FAILURE_EVENT",
            "severity": "MEDIUM",
            "slaMinutes": 15,
            "reminderEveryMinutes": 15,
            "escalateAfterMinutes": 45,
        }

        incidents.append({
            "incidentId": _incident_id(row),
            "romeoId": str(row.get("RomeoId") or ""),
            "detectedAt": row.get("Timestamp"),
            "incidentType": rule["type"],
            "severity": rule["severity"],
            "sourceReportCode": code,
            "sourceReportText": row.get("ReportTextRaw"),
            "sourceReportFail": fail,
            "programCandidateId": row.get("ReportId1Raw"),
            "objectCandidateId": row.get("ReportId2NameRaw") or row.get("ReportId2Raw"),
            "sourceObjectIdRaw": row.get("ReportId2Raw"),
            "status": "DETECTED",
            "slaPolicy": {
                "responseDueMinutes": rule["slaMinutes"],
                "reminderEveryMinutes": rule["reminderEveryMinutes"],
                "escalateAfterMinutes": rule["escalateAfterMinutes"],
                "coordinatorEscalateAfterMinutes": rule.get("coordinatorEscalateAfterMinutes", rule["escalateAfterMinutes"] + rule["reminderEveryMinutes"]),
                "repeatUntilResolved": True,
            },
            "notificationPlan": {
                "channel": "WHATSAPP",
                "enabled": False,
                "repeatUntilResolved": True,
                "requiresAssignee": True,
            },
            "requiresPhotoEvidence": True,
            "requiresObservation": True,
            "requiresResolutionValidation": True,
            "mappingStatus": "CANDIDATE",
        })

    by_type = Counter(item["incidentType"] for item in incidents)
    by_romeo = Counter(item["romeoId"] for item in incidents)
    by_severity = Counter(item["severity"] for item in incidents)

    return {
        "success": True,
        "sourceFile": str(source),
        "incidentCount": len(incidents),
        "byType": dict(sorted(by_type.items())),
        "byRomeo": dict(sorted(by_romeo.items())),
        "bySeverity": dict(sorted(by_severity.items())),
        "incidents": incidents,
        "lifecycle": [
            "DETECTED", "NOTIFIED", "WAITING_RESPONSE", "IN_PROGRESS",
            "PENDING_VALIDATION", "ESCALATED", "RESOLVED", "CLOSED"
        ],
        "interpretationStatus": "CANDIDATE",
        "safety": {
            "sendsWhatsApp": False,
            "createsProductionIncidents": False,
            "canUseForLogicValidation": True,
        },
    }
