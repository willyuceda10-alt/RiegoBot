from __future__ import annotations

import json
import sqlite3
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .config import load_config
from .incident_workflow import build_incident_episodes, build_incident_sla_plan
from .routing import build_incident_routing_candidate

ACTIVE_STATUSES = {
    "DETECTED",
    "NOTIFIED",
    "WAITING_RESPONSE",
    "IN_PROGRESS",
    "PENDING_VALIDATION",
    "ESCALATED",
}

TERMINAL_STATUSES = {"RESOLVED", "CLOSED"}


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _store_path(project_root: Path, config: dict[str, Any]) -> Path:
    persistence = config.get("incidentPersistence") or {}
    raw = str(persistence.get("path") or "runtime/incident_state.db")
    path = Path(raw)
    if not path.is_absolute():
        path = project_root / path
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def _connect(path: Path) -> sqlite3.Connection:
    connection = sqlite3.connect(path)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    connection.execute("PRAGMA journal_mode = WAL")
    return connection


def _init_schema(connection: sqlite3.Connection) -> None:
    connection.executescript(
        """
        CREATE TABLE IF NOT EXISTS incidents (
            episode_id TEXT PRIMARY KEY,
            romeo_id TEXT NOT NULL,
            fundo_id TEXT,
            incident_type TEXT NOT NULL,
            severity TEXT NOT NULL,
            program_candidate_id TEXT,
            object_candidate_id TEXT,
            first_detected_at TEXT NOT NULL,
            last_signal_at TEXT NOT NULL,
            signal_count INTEGER NOT NULL,
            status TEXT NOT NULL,
            routing_status TEXT,
            primary_user_id TEXT,
            supervisor_user_id TEXT,
            coordinator_user_id TEXT,
            response_due_at TEXT,
            supervisor_escalation_at TEXT,
            coordinator_escalation_at TEXT,
            requires_photo_evidence INTEGER NOT NULL DEFAULT 1,
            requires_observation INTEGER NOT NULL DEFAULT 1,
            requires_resolution_validation INTEGER NOT NULL DEFAULT 1,
            mapping_status TEXT NOT NULL DEFAULT 'CANDIDATE',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS incident_events (
            event_id INTEGER PRIMARY KEY AUTOINCREMENT,
            episode_id TEXT NOT NULL,
            event_type TEXT NOT NULL,
            from_status TEXT,
            to_status TEXT,
            occurred_at TEXT NOT NULL,
            actor_type TEXT NOT NULL,
            actor_id TEXT,
            observation TEXT,
            metadata_json TEXT,
            FOREIGN KEY (episode_id) REFERENCES incidents(episode_id)
        );

        CREATE INDEX IF NOT EXISTS idx_incidents_status
            ON incidents(status);
        CREATE INDEX IF NOT EXISTS idx_incidents_romeo
            ON incidents(romeo_id);
        CREATE INDEX IF NOT EXISTS idx_incident_events_episode
            ON incident_events(episode_id, occurred_at);
        """
    )


def _route_map(project_root: Path) -> dict[str, dict[str, Any]]:
    payload = build_incident_routing_candidate(project_root)
    if not payload.get("success"):
        return {}
    return {
        str(route.get("episodeId")): route
        for route in payload.get("routes", [])
        if isinstance(route, dict) and route.get("episodeId")
    }


def _sla_map(project_root: Path) -> dict[str, dict[str, Any]]:
    payload = build_incident_sla_plan(project_root)
    if not payload.get("success"):
        return {}
    return {
        str(plan.get("episodeId")): plan
        for plan in payload.get("plans", [])
        if isinstance(plan, dict) and plan.get("episodeId")
    }


def sync_incident_store_candidate(project_root: Path) -> dict[str, Any]:
    config = load_config(project_root)
    episodes_payload = build_incident_episodes(project_root)
    if not episodes_payload.get("success"):
        return episodes_payload

    routes = _route_map(project_root)
    sla = _sla_map(project_root)
    db_path = _store_path(project_root, config)
    now = _utc_now()

    inserted = 0
    updated = 0
    preserved_status = 0

    with _connect(db_path) as connection:
        _init_schema(connection)

        for episode in episodes_payload.get("episodes", []):
            episode_id = str(episode.get("episodeId") or "")
            if not episode_id:
                continue

            route = routes.get(episode_id, {})
            plan = sla.get(episode_id, {})
            existing = connection.execute(
                "SELECT status FROM incidents WHERE episode_id = ?",
                (episode_id,),
            ).fetchone()

            status = str(existing["status"]) if existing else "DETECTED"
            if existing:
                preserved_status += 1

            primary = route.get("primaryAssignee") or {}
            supervisor = route.get("supervisorAssignee") or {}
            coordinator = route.get("coordinatorAssignee") or {}

            values = (
                episode_id,
                str(episode.get("romeoId") or ""),
                episode.get("fundoId"),
                str(episode.get("incidentType") or ""),
                str(episode.get("severity") or ""),
                str(episode.get("programCandidateId") or "") or None,
                str(episode.get("objectCandidateId") or "") or None,
                str(episode.get("firstDetectedAt") or ""),
                str(episode.get("lastSignalAt") or ""),
                int(episode.get("signalCount") or 1),
                status,
                route.get("routingStatus"),
                primary.get("userId"),
                supervisor.get("userId"),
                coordinator.get("userId"),
                plan.get("responseDueAt"),
                plan.get("supervisorEscalationAt"),
                plan.get("coordinatorEscalationAt"),
                1 if episode.get("requiresPhotoEvidence", True) else 0,
                1 if episode.get("requiresObservation", True) else 0,
                1 if episode.get("requiresResolutionValidation", True) else 0,
                str(episode.get("mappingStatus") or "CANDIDATE"),
                now,
                now,
            )

            if existing is None:
                connection.execute(
                    """
                    INSERT INTO incidents (
                        episode_id, romeo_id, fundo_id, incident_type, severity,
                        program_candidate_id, object_candidate_id,
                        first_detected_at, last_signal_at, signal_count, status,
                        routing_status, primary_user_id, supervisor_user_id,
                        coordinator_user_id, response_due_at,
                        supervisor_escalation_at, coordinator_escalation_at,
                        requires_photo_evidence, requires_observation,
                        requires_resolution_validation, mapping_status,
                        created_at, updated_at
                    )
                    VALUES (
                        ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                        ?, ?, ?, ?, ?, ?
                    )
                    """,
                    values,
                )
                connection.execute(
                    """
                    INSERT INTO incident_events (
                        episode_id, event_type, from_status, to_status,
                        occurred_at, actor_type, actor_id, observation, metadata_json
                    )
                    VALUES (?, 'INCIDENT_CREATED', NULL, 'DETECTED', ?, 'SYSTEM', NULL, NULL, ?)
                    """,
                    (
                        episode_id,
                        now,
                        json.dumps(
                            {
                                "source": "DREAM_CANDIDATE",
                                "signalCount": int(episode.get("signalCount") or 1),
                                "routingStatus": route.get("routingStatus"),
                            },
                            ensure_ascii=False,
                        ),
                    ),
                )
                inserted += 1
            else:
                connection.execute(
                    """
                    UPDATE incidents SET
                        romeo_id = ?,
                        fundo_id = ?,
                        incident_type = ?,
                        severity = ?,
                        program_candidate_id = ?,
                        object_candidate_id = ?,
                        first_detected_at = ?,
                        last_signal_at = ?,
                        signal_count = ?,
                        routing_status = ?,
                        primary_user_id = ?,
                        supervisor_user_id = ?,
                        coordinator_user_id = ?,
                        response_due_at = ?,
                        supervisor_escalation_at = ?,
                        coordinator_escalation_at = ?,
                        requires_photo_evidence = ?,
                        requires_observation = ?,
                        requires_resolution_validation = ?,
                        mapping_status = ?,
                        updated_at = ?
                    WHERE episode_id = ?
                    """,
                    (
                        values[1], values[2], values[3], values[4], values[5],
                        values[6], values[7], values[8], values[9], values[11],
                        values[12], values[13], values[14], values[15], values[16],
                        values[17], values[18], values[19], values[20], values[21],
                        now, episode_id,
                    ),
                )
                updated += 1

        connection.commit()

        total = connection.execute("SELECT COUNT(*) AS n FROM incidents").fetchone()["n"]
        event_count = connection.execute(
            "SELECT COUNT(*) AS n FROM incident_events"
        ).fetchone()["n"]

    return {
        "success": True,
        "backend": "sqlite",
        "databasePath": str(db_path),
        "sourceEpisodeCount": int(episodes_payload.get("episodeCount") or 0),
        "insertedIncidents": inserted,
        "updatedIncidents": updated,
        "existingStatusesPreserved": preserved_status,
        "storedIncidentCount": int(total),
        "storedEventCount": int(event_count),
        "idempotent": True,
        "safety": {
            "sendsWhatsApp": False,
            "productionBackend": False,
            "migrationTarget": "AZURE_POSTGRESQL",
        },
    }


def incident_store_summary(project_root: Path) -> dict[str, Any]:
    config = load_config(project_root)
    db_path = _store_path(project_root, config)
    if not db_path.exists():
        return {
            "success": False,
            "error": "La base durable de incidencias aun no existe. Ejecute incident-sync-candidate.",
            "databasePath": str(db_path),
        }

    with _connect(db_path) as connection:
        _init_schema(connection)
        rows = [
            dict(row)
            for row in connection.execute(
                """
                SELECT episode_id, romeo_id, fundo_id, incident_type, severity,
                       first_detected_at, last_signal_at, signal_count, status,
                       routing_status, primary_user_id, supervisor_user_id,
                       coordinator_user_id, response_due_at,
                       supervisor_escalation_at, coordinator_escalation_at,
                       updated_at
                FROM incidents
                ORDER BY first_detected_at DESC
                """
            ).fetchall()
        ]
        event_count = int(
            connection.execute(
                "SELECT COUNT(*) AS n FROM incident_events"
            ).fetchone()["n"]
        )

    by_status = Counter(str(row["status"]) for row in rows)
    by_type = Counter(str(row["incident_type"]) for row in rows)
    by_romeo = Counter(str(row["romeo_id"]) for row in rows)
    unassigned = sum(1 for row in rows if row.get("routing_status") == "UNASSIGNED")
    active = sum(1 for row in rows if row.get("status") in ACTIVE_STATUSES)

    return {
        "success": True,
        "backend": "sqlite",
        "databasePath": str(db_path),
        "incidentCount": len(rows),
        "eventCount": event_count,
        "activeIncidentCount": active,
        "unassignedIncidentCount": unassigned,
        "byStatus": dict(sorted(by_status.items())),
        "byType": dict(sorted(by_type.items())),
        "byRomeo": dict(sorted(by_romeo.items())),
        "incidents": rows,
        "migrationReadyModel": {
            "incidents": True,
            "incidentEvents": True,
            "target": "AZURE_POSTGRESQL",
        },
    }
