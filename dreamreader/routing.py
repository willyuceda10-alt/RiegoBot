from __future__ import annotations

from collections import Counter
from datetime import datetime, time
from pathlib import Path
from typing import Any

from .config import load_config
from .incident_workflow import build_incident_episodes

ROLE_ORDER = ("REGADOR", "SUPERVISOR", "COORDINADOR")


def _parse_hhmm(value: Any) -> time | None:
    if not value:
        return None
    try:
        hour, minute = str(value).split(":", 1)
        return time(int(hour), int(minute))
    except (TypeError, ValueError):
        return None


def _parse_timestamp(value: Any) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value))
    except ValueError:
        return None


def _matches_list(value: str, allowed: Any) -> bool:
    if allowed in (None, [], ""):
        return True
    values = {str(item) for item in allowed if item is not None}
    return "*" in values or value in values


def _matches_shift(timestamp: datetime | None, shift: Any) -> bool:
    if not isinstance(shift, dict) or not shift:
        return True
    if timestamp is None:
        return False

    days = shift.get("days")
    if days not in (None, []):
        valid_days = {int(day) for day in days}
        if timestamp.weekday() not in valid_days:
            return False

    start = _parse_hhmm(shift.get("startTime"))
    end = _parse_hhmm(shift.get("endTime"))
    if start is None or end is None:
        return True

    current = timestamp.time()
    if start <= end:
        return start <= current < end
    return current >= start or current < end


def _user_index(users: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {
        str(user.get("userId")): user
        for user in users
        if isinstance(user, dict) and user.get("userId")
    }


def _candidate_assignments(
    episode: dict[str, Any],
    role: str,
    assignments: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    romeo_id = str(episode.get("romeoId") or "")
    incident_type = str(episode.get("incidentType") or "")
    fundo_id = str(episode.get("fundoId") or "")
    detected_at = _parse_timestamp(episode.get("firstDetectedAt"))

    matches = []
    for assignment in assignments:
        if not isinstance(assignment, dict) or not assignment.get("enabled", True):
            continue
        if str(assignment.get("role") or "").upper() != role:
            continue
        if not _matches_list(romeo_id, assignment.get("romeoIds")):
            continue
        if not _matches_list(incident_type, assignment.get("incidentTypes")):
            continue
        if fundo_id and not _matches_list(fundo_id, assignment.get("fundoIds")):
            continue
        if not _matches_shift(detected_at, assignment.get("shift")):
            continue
        matches.append(assignment)

    matches.sort(
        key=lambda item: (
            -int(item.get("priority") or 0),
            str(item.get("assignmentId") or ""),
        )
    )
    return matches


def route_episode(
    episode: dict[str, Any],
    users: list[dict[str, Any]],
    assignments: list[dict[str, Any]],
) -> dict[str, Any]:
    users_by_id = _user_index(users)
    selected: dict[str, dict[str, Any] | None] = {}
    missing_roles: list[str] = []

    for role in ROLE_ORDER:
        candidates = _candidate_assignments(episode, role, assignments)
        chosen = None
        for assignment in candidates:
            user = users_by_id.get(str(assignment.get("userId") or ""))
            if user is None or not user.get("enabled", True):
                continue
            chosen = {
                "assignmentId": assignment.get("assignmentId"),
                "userId": user.get("userId"),
                "displayName": user.get("displayName"),
                "role": role,
                "whatsappNumber": user.get("whatsappNumber"),
                "priority": int(assignment.get("priority") or 0),
                "scope": {
                    "romeoIds": assignment.get("romeoIds", []),
                    "fundoIds": assignment.get("fundoIds", []),
                    "incidentTypes": assignment.get("incidentTypes", []),
                    "shift": assignment.get("shift"),
                },
            }
            break

        selected[role] = chosen
        if chosen is None:
            missing_roles.append(role)

    primary = selected["REGADOR"]
    status = "ROUTED" if primary is not None else "UNASSIGNED"

    return {
        "episodeId": episode.get("episodeId"),
        "romeoId": episode.get("romeoId"),
        "fundoId": episode.get("fundoId"),
        "incidentType": episode.get("incidentType"),
        "severity": episode.get("severity"),
        "firstDetectedAt": episode.get("firstDetectedAt"),
        "routingStatus": status,
        "primaryAssignee": primary,
        "supervisorAssignee": selected["SUPERVISOR"],
        "coordinatorAssignee": selected["COORDINADOR"],
        "missingRoles": missing_roles,
        "canSendInitialWhatsApp": bool(
            primary is not None and primary.get("whatsappNumber")
        ),
        "mappingStatus": "CANDIDATE",
    }


def build_incident_routing_candidate(project_root: Path) -> dict[str, Any]:
    episodes_payload = build_incident_episodes(project_root)
    if not episodes_payload.get("success"):
        return episodes_payload

    config = load_config(project_root)
    routing_cfg = config.get("routing") or {}
    users = [
        user for user in routing_cfg.get("users", [])
        if isinstance(user, dict)
    ]
    assignments = [
        assignment for assignment in routing_cfg.get("assignments", [])
        if isinstance(assignment, dict)
    ]

    routes = [
        route_episode(episode, users, assignments)
        for episode in episodes_payload.get("episodes", [])
    ]

    by_status = Counter(route["routingStatus"] for route in routes)
    missing_role_counts = Counter(
        role
        for route in routes
        for role in route.get("missingRoles", [])
    )

    return {
        "success": True,
        "episodeCount": len(routes),
        "configuredUserCount": len(users),
        "configuredAssignmentCount": len(assignments),
        "byRoutingStatus": dict(sorted(by_status.items())),
        "missingRoleCounts": dict(sorted(missing_role_counts.items())),
        "routes": routes,
        "routingContract": {
            "primaryRole": "REGADOR",
            "supervisorRole": "SUPERVISOR",
            "coordinatorRole": "COORDINADOR",
            "scopesSupported": [
                "romeoIds",
                "fundoIds",
                "incidentTypes",
                "shift",
            ],
            "prioritySupported": True,
            "unassignedEpisodesAreBlockedFromWhatsApp": True,
        },
        "safety": {
            "sendsWhatsApp": False,
            "routingOnly": True,
            "doesNotInventContacts": True,
        },
    }
