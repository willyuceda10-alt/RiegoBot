from __future__ import annotations

import hashlib
from collections import Counter
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from .config import load_config
from .incidents import build_incident_candidates


def _parse_ts(value: Any) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value))
    except ValueError:
        return None


def _episode_id(key: tuple[str, str, str, str], first_detected: str) -> str:
    raw = "|".join([*key, first_detected])
    return "EPI-" + hashlib.sha1(raw.encode("utf-8")).hexdigest()[:12].upper()


def build_incident_episodes(project_root: Path) -> dict[str, Any]:
    raw = build_incident_candidates(project_root)
    if not raw.get("success"):
        return raw

    config = load_config(project_root)
    incident_cfg = config.get("incidents", {})
    gap_minutes = float(incident_cfg.get("episodeGapMinutes", 30))

    signals = [x for x in raw.get("incidents", []) if isinstance(x, dict)]
    signals.sort(key=lambda x: _parse_ts(x.get("detectedAt")) or datetime.min)

    open_by_key: dict[tuple[str, str, str, str], dict[str, Any]] = {}
    episodes: list[dict[str, Any]] = []

    for signal in signals:
        ts = _parse_ts(signal.get("detectedAt"))
        if ts is None:
            continue
        key = (
            str(signal.get("romeoId") or ""),
            str(signal.get("incidentType") or ""),
            str(signal.get("programCandidateId") or ""),
            str(signal.get("objectCandidateId") or ""),
        )
        current = open_by_key.get(key)
        if current is not None:
            last_ts = _parse_ts(current.get("lastSignalAt"))
            if last_ts is not None and (ts - last_ts).total_seconds() / 60.0 <= gap_minutes:
                current["lastSignalAt"] = signal.get("detectedAt")
                current["signalCount"] += 1
                current["sourceSignalIds"].append(signal.get("incidentId"))
                current["durationMinutes"] = round(
                    (ts - _parse_ts(current["firstDetectedAt"])).total_seconds() / 60.0,
                    2,
                )
                continue

        episode = {
            "episodeId": _episode_id(key, str(signal.get("detectedAt") or "")),
            "romeoId": signal.get("romeoId"),
            "incidentType": signal.get("incidentType"),
            "severity": signal.get("severity"),
            "programCandidateId": signal.get("programCandidateId"),
            "objectCandidateId": signal.get("objectCandidateId"),
            "firstDetectedAt": signal.get("detectedAt"),
            "lastSignalAt": signal.get("detectedAt"),
            "signalCount": 1,
            "durationMinutes": 0.0,
            "sourceSignalIds": [signal.get("incidentId")],
            "status": "DETECTED",
            "slaPolicy": signal.get("slaPolicy"),
            "notificationPlan": {
                **(signal.get("notificationPlan") or {}),
                "primaryRole": "REGADOR",
                "escalationRoles": ["SUPERVISOR", "COORDINADOR"],
            },
            "requiresPhotoEvidence": signal.get("requiresPhotoEvidence", False),
            "requiresObservation": signal.get("requiresObservation", True),
            "requiresResolutionValidation": signal.get("requiresResolutionValidation", True),
            "mappingStatus": "CANDIDATE",
        }
        episodes.append(episode)
        open_by_key[key] = episode

    episodes.sort(key=lambda x: _parse_ts(x.get("firstDetectedAt")) or datetime.min, reverse=True)
    by_type = Counter(x["incidentType"] for x in episodes)
    by_romeo = Counter(x["romeoId"] for x in episodes)
    by_severity = Counter(x["severity"] for x in episodes)

    return {
        "success": True,
        "sourceRowCount": raw.get("sourceRowCount"),
        "duplicateSignalRowsDropped": raw.get("duplicateSignalRowsDropped", 0),
        "rawSignalCount": len(signals),
        "episodeCount": len(episodes),
        "episodeGapMinutes": gap_minutes,
        "compressionRatio": round((len(signals) / len(episodes)), 2) if episodes else None,
        "byType": dict(sorted(by_type.items())),
        "byRomeo": dict(sorted(by_romeo.items())),
        "bySeverity": dict(sorted(by_severity.items())),
        "episodes": episodes,
        "interpretationStatus": "CANDIDATE",
        "safeNote": (
            "Las filas duplicadas exactas se eliminan antes de agrupar. Las senales repetidas "
            "del mismo Romeo/tipo/programa/objeto forman un episodio si la separacion no supera "
            "episodeGapMinutes. Esto valida la logica y no afirma que Dream haya cerrado/resuelto "
            "la incidencia."
        ),
    }


def _iso_add(value: str, minutes: float) -> str | None:
    ts = _parse_ts(value)
    return (ts + timedelta(minutes=minutes)).isoformat() if ts else None


def _recipient_roles(offset: float, supervisor_after: float, coordinator_after: float) -> list[str]:
    recipients = ["REGADOR"]
    if offset >= supervisor_after:
        recipients.append("SUPERVISOR")
    if offset >= coordinator_after:
        recipients.append("COORDINADOR")
    return recipients


def build_sla_timeline(
    detected: str,
    response_due: float,
    cadence: float,
    supervisor_after: float,
    coordinator_after: float,
    preview_count: int,
) -> list[dict[str, Any]]:
    timeline: list[dict[str, Any]] = [
        {
            "offsetMinutes": 0.0,
            "at": detected,
            "action": "SEND_INITIAL_ALERT",
            "recipients": ["REGADOR"],
            "targetStatus": "NOTIFIED",
        }
    ]

    reminder_offsets: set[float] = set()
    for n in range(1, preview_count + 1):
        offset = response_due + cadence * (n - 1)
        reminder_offsets.add(offset)
        recipients = _recipient_roles(offset, supervisor_after, coordinator_after)
        timeline.append(
            {
                "offsetMinutes": offset,
                "at": _iso_add(detected, offset),
                "action": f"REMINDER_{n}",
                "recipients": recipients,
                "targetStatus": "ESCALATED" if len(recipients) > 1 else "WAITING_RESPONSE",
                "responseSlaExpired": True,
            }
        )

    # If an escalation threshold already coincides with a reminder, that reminder
    # carries the expanded recipients and no second WhatsApp notification is added.
    for offset, action, recipients in (
        (supervisor_after, "ESCALATE_SUPERVISOR", ["REGADOR", "SUPERVISOR"]),
        (
            coordinator_after,
            "ESCALATE_COORDINATOR",
            ["REGADOR", "SUPERVISOR", "COORDINADOR"],
        ),
    ):
        if offset in reminder_offsets:
            continue
        timeline.append(
            {
                "offsetMinutes": offset,
                "at": _iso_add(detected, offset),
                "action": action,
                "recipients": recipients,
                "targetStatus": "ESCALATED",
                "responseSlaExpired": True,
            }
        )

    timeline.sort(key=lambda x: (float(x["offsetMinutes"]), str(x["action"])))
    return timeline


def build_incident_sla_plan(project_root: Path) -> dict[str, Any]:
    episode_payload = build_incident_episodes(project_root)
    if not episode_payload.get("success"):
        return episode_payload

    config = load_config(project_root)
    incident_cfg = config.get("incidents", {})
    preview_count = int(incident_cfg.get("slaPreviewReminders", 5))

    plans = []
    for episode in episode_payload.get("episodes", []):
        policy = episode.get("slaPolicy") or {}
        detected = str(episode.get("firstDetectedAt") or "")
        response_due = float(policy.get("responseDueMinutes") or 10)
        cadence = float(policy.get("reminderEveryMinutes") or 10)
        supervisor_after = float(policy.get("escalateAfterMinutes") or 30)
        coordinator_after = float(
            policy.get("coordinatorEscalateAfterMinutes") or (supervisor_after + cadence)
        )

        timeline = build_sla_timeline(
            detected,
            response_due,
            cadence,
            supervisor_after,
            coordinator_after,
            preview_count,
        )

        plans.append(
            {
                "episodeId": episode.get("episodeId"),
                "romeoId": episode.get("romeoId"),
                "incidentType": episode.get("incidentType"),
                "severity": episode.get("severity"),
                "firstDetectedAt": detected,
                "signalCount": episode.get("signalCount"),
                "slaPolicy": {
                    **policy,
                    "coordinatorEscalateAfterMinutes": coordinator_after,
                },
                "responseDueAt": _iso_add(detected, response_due),
                "supervisorEscalationAt": _iso_add(detected, supervisor_after),
                "coordinatorEscalationAt": _iso_add(detected, coordinator_after),
                "timelinePreview": timeline,
                "stopCondition": "RESOLVED_OR_CLOSED_ONLY",
                "acknowledgementDoesNotClose": True,
                "resolutionRequirements": {
                    "observation": bool(episode.get("requiresObservation", True)),
                    "photoEvidence": bool(episode.get("requiresPhotoEvidence", False)),
                    "technicalValidationWhenPossible": bool(episode.get("requiresResolutionValidation", True)),
                },
                "whatsappEnabled": False,
                "mappingStatus": "CANDIDATE",
            }
        )

    return {
        "success": True,
        "sourceRowCount": episode_payload.get("sourceRowCount"),
        "duplicateSignalRowsDropped": episode_payload.get("duplicateSignalRowsDropped", 0),
        "episodeCount": len(plans),
        "slaPreviewReminders": preview_count,
        "plans": plans,
        "runtimeContract": {
            "repeatUntilResolved": True,
            "acknowledgementStopsReminders": False,
            "inProgressStopsReminders": False,
            "resolvedOrClosedStopsReminders": True,
            "initialRecipientRole": "REGADOR",
            "escalationRoles": ["SUPERVISOR", "COORDINADOR"],
            "duplicateNotificationsAtSameThreshold": False,
        },
        "safety": {
            "sendsWhatsApp": False,
            "simulationOnly": True,
        },
    }
