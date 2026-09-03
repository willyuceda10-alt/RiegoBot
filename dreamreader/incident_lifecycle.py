from __future__ import annotations

import hashlib
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .config import load_config
from .incident_store import _connect, _init_schema, _store_path
from .incident_workflow import build_incident_sla_plan
from .routing import build_incident_routing_candidate

ALLOWED_TRANSITIONS: dict[str, set[str]] = {
    "DETECTED": {"NOTIFIED", "IN_PROGRESS", "ESCALATED"},
    "NOTIFIED": {"WAITING_RESPONSE", "IN_PROGRESS", "ESCALATED"},
    "WAITING_RESPONSE": {"IN_PROGRESS", "ESCALATED"},
    "IN_PROGRESS": {"PENDING_VALIDATION", "ESCALATED"},
    "ESCALATED": {"IN_PROGRESS", "PENDING_VALIDATION"},
    "PENDING_VALIDATION": {"IN_PROGRESS", "RESOLVED"},
    "RESOLVED": {"CLOSED"},
    "CLOSED": set(),
}

TERMINAL_STATUSES = {"RESOLVED", "CLOSED"}


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _init_lifecycle_schema(connection) -> None:
    _init_schema(connection)
    connection.executescript(
        """
        CREATE TABLE IF NOT EXISTS incident_evidence (
            evidence_id INTEGER PRIMARY KEY AUTOINCREMENT,
            episode_id TEXT NOT NULL,
            evidence_type TEXT NOT NULL,
            storage_ref TEXT NOT NULL,
            file_name TEXT,
            mime_type TEXT,
            actor_id TEXT,
            received_at TEXT NOT NULL,
            metadata_json TEXT,
            FOREIGN KEY (episode_id) REFERENCES incidents(episode_id)
        );

        CREATE TABLE IF NOT EXISTS notification_outbox (
            outbox_id TEXT PRIMARY KEY,
            episode_id TEXT NOT NULL,
            channel TEXT NOT NULL,
            action TEXT NOT NULL,
            recipient_role TEXT NOT NULL,
            recipient_user_id TEXT,
            scheduled_at TEXT NOT NULL,
            status TEXT NOT NULL,
            attempt_count INTEGER NOT NULL DEFAULT 0,
            last_attempt_at TEXT,
            sent_at TEXT,
            provider_message_id TEXT,
            payload_json TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            FOREIGN KEY (episode_id) REFERENCES incidents(episode_id)
        );

        CREATE INDEX IF NOT EXISTS idx_incident_evidence_episode
            ON incident_evidence(episode_id, received_at);
        CREATE INDEX IF NOT EXISTS idx_notification_outbox_status
            ON notification_outbox(status, scheduled_at);
        CREATE INDEX IF NOT EXISTS idx_notification_outbox_episode
            ON notification_outbox(episode_id, scheduled_at);
        """
    )


def lifecycle_contract() -> dict[str, Any]:
    return {
        "success": True,
        "allowedTransitions": {
            status: sorted(targets)
            for status, targets in ALLOWED_TRANSITIONS.items()
        },
        "whatsappSemantics": {
            "acknowledgedPhraseExample": "Ya estoy revisando",
            "acknowledgementTargetStatus": "IN_PROGRESS",
            "acknowledgementClosesIncident": False,
            "inProgressStopsReminders": False,
            "resolvedOrClosedStopsReminders": True,
        },
        "resolutionRequirements": {
            "observationDefaultRequired": True,
            "photoEvidenceDefaultRequired": False,
            "photoEvidence": "CONFIGURABLE_BY_INCIDENT_TYPE",
            "validationBeforeResolved": True,
            "futurePolicyAuthority": "AZURE_CENTRAL_POLICY",
        },
        "outbox": {
            "channel": "WHATSAPP",
            "idempotent": True,
            "testReplayStatus": "BLOCKED_TEST_REPLAY",
            "unassignedStatus": "BLOCKED_UNASSIGNED",
            "realSendingEnabled": False,
        },
    }


def _append_event(
    connection,
    episode_id: str,
    event_type: str,
    from_status: str | None,
    to_status: str | None,
    actor_type: str,
    actor_id: str | None,
    observation: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> None:
    connection.execute(
        """
        INSERT INTO incident_events (
            episode_id, event_type, from_status, to_status, occurred_at,
            actor_type, actor_id, observation, metadata_json
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            episode_id,
            event_type,
            from_status,
            to_status,
            _utc_now(),
            actor_type,
            actor_id,
            observation,
            json.dumps(metadata or {}, ensure_ascii=False),
        ),
    )


def _has_observation(connection, episode_id: str) -> bool:
    row = connection.execute(
        """
        SELECT 1
        FROM incident_events
        WHERE episode_id = ?
          AND observation IS NOT NULL
          AND TRIM(observation) <> ''
        LIMIT 1
        """,
        (episode_id,),
    ).fetchone()
    return row is not None


def _has_photo(connection, episode_id: str) -> bool:
    row = connection.execute(
        """
        SELECT 1
        FROM incident_evidence
        WHERE episode_id = ?
          AND evidence_type = 'PHOTO'
        LIMIT 1
        """,
        (episode_id,),
    ).fetchone()
    return row is not None


def transition_incident(
    project_root: Path,
    episode_id: str,
    to_status: str,
    *,
    actor_type: str,
    actor_id: str | None,
    observation: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    config = load_config(project_root)
    db_path = _store_path(project_root, config)
    if not db_path.exists():
        return {"success": False, "error": "Incident store does not exist."}

    target = str(to_status).upper()
    with _connect(db_path) as connection:
        _init_lifecycle_schema(connection)
        row = connection.execute(
            """
            SELECT episode_id, status, requires_photo_evidence,
                   requires_observation, requires_resolution_validation
            FROM incidents
            WHERE episode_id = ?
            """,
            (episode_id,),
        ).fetchone()
        if row is None:
            return {"success": False, "error": "Incident not found.", "episodeId": episode_id}

        current = str(row["status"])
        if target == current:
            return {
                "success": True,
                "episodeId": episode_id,
                "fromStatus": current,
                "toStatus": target,
                "changed": False,
                "idempotent": True,
            }

        allowed = ALLOWED_TRANSITIONS.get(current, set())
        if target not in allowed:
            return {
                "success": False,
                "error": "Invalid incident transition.",
                "episodeId": episode_id,
                "fromStatus": current,
                "toStatus": target,
                "allowedTargets": sorted(allowed),
            }

        if target in {"PENDING_VALIDATION", "RESOLVED"}:
            missing = []
            if bool(row["requires_observation"]) and not (
                (observation and observation.strip()) or _has_observation(connection, episode_id)
            ):
                missing.append("observation")
            if bool(row["requires_photo_evidence"]) and not _has_photo(connection, episode_id):
                missing.append("photoEvidence")
            if missing:
                return {
                    "success": False,
                    "error": "Resolution evidence requirements are not satisfied.",
                    "episodeId": episode_id,
                    "missingRequirements": missing,
                }

        now = _utc_now()
        connection.execute(
            "UPDATE incidents SET status = ?, updated_at = ? WHERE episode_id = ?",
            (target, now, episode_id),
        )
        _append_event(
            connection,
            episode_id,
            "STATUS_CHANGED",
            current,
            target,
            actor_type,
            actor_id,
            observation,
            metadata,
        )
        connection.commit()

    return {
        "success": True,
        "episodeId": episode_id,
        "fromStatus": current,
        "toStatus": target,
        "changed": True,
    }


def acknowledge_incident(
    project_root: Path,
    episode_id: str,
    *,
    actor_id: str | None,
    observation: str | None = None,
) -> dict[str, Any]:
    return transition_incident(
        project_root,
        episode_id,
        "IN_PROGRESS",
        actor_type="USER",
        actor_id=actor_id,
        observation=observation,
        metadata={"source": "WHATSAPP_CANDIDATE", "semantic": "ACKNOWLEDGED"},
    )


def add_incident_evidence(
    project_root: Path,
    episode_id: str,
    *,
    evidence_type: str,
    storage_ref: str,
    file_name: str | None,
    mime_type: str | None,
    actor_id: str | None,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    config = load_config(project_root)
    db_path = _store_path(project_root, config)
    if not db_path.exists():
        return {"success": False, "error": "Incident store does not exist."}

    with _connect(db_path) as connection:
        _init_lifecycle_schema(connection)
        exists = connection.execute(
            "SELECT 1 FROM incidents WHERE episode_id = ?",
            (episode_id,),
        ).fetchone()
        if exists is None:
            return {"success": False, "error": "Incident not found.", "episodeId": episode_id}

        now = _utc_now()
        cursor = connection.execute(
            """
            INSERT INTO incident_evidence (
                episode_id, evidence_type, storage_ref, file_name, mime_type,
                actor_id, received_at, metadata_json
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                episode_id,
                str(evidence_type).upper(),
                storage_ref,
                file_name,
                mime_type,
                actor_id,
                now,
                json.dumps(metadata or {}, ensure_ascii=False),
            ),
        )
        _append_event(
            connection,
            episode_id,
            "EVIDENCE_RECEIVED",
            None,
            None,
            "USER",
            actor_id,
            None,
            {
                "evidenceId": cursor.lastrowid,
                "evidenceType": str(evidence_type).upper(),
                "storageRef": storage_ref,
            },
        )
        connection.commit()

    return {
        "success": True,
        "episodeId": episode_id,
        "evidenceId": cursor.lastrowid,
        "evidenceType": str(evidence_type).upper(),
    }


def _outbox_id(episode_id: str, action: str, role: str, scheduled_at: str) -> str:
    raw = "|".join([episode_id, action, role, scheduled_at])
    return "OUT-" + hashlib.sha1(raw.encode("utf-8")).hexdigest()[:16].upper()


def sync_notification_outbox_candidate(project_root: Path) -> dict[str, Any]:
    config = load_config(project_root)
    db_path = _store_path(project_root, config)
    if not db_path.exists():
        return {
            "success": False,
            "error": "Incident store does not exist. Run incident-sync-candidate first.",
        }

    plan_payload = build_incident_sla_plan(project_root)
    route_payload = build_incident_routing_candidate(project_root)
    if not plan_payload.get("success") or not route_payload.get("success"):
        return {"success": False, "error": "Could not build SLA/routing candidate data."}

    plans = {
        str(plan.get("episodeId")): plan
        for plan in plan_payload.get("plans", [])
        if isinstance(plan, dict) and plan.get("episodeId")
    }
    routes = {
        str(route.get("episodeId")): route
        for route in route_payload.get("routes", [])
        if isinstance(route, dict) and route.get("episodeId")
    }

    inserted = 0
    updated = 0
    pending = 0
    blocked = 0
    blocked_test_replay = 0
    blocked_unassigned = 0
    skipped_terminal = 0
    now = _utc_now()

    notifications_cfg = config.get("notifications") or {}
    operational_cfg = config.get("operationalState") or {}
    test_replay_mode = (
        str(notifications_cfg.get("mode") or "candidate").lower() != "production"
        or bool(operational_cfg.get("allowStaleForTesting", False))
    )

    with _connect(db_path) as connection:
        _init_lifecycle_schema(connection)
        incidents = connection.execute(
            "SELECT episode_id, status FROM incidents"
        ).fetchall()

        for incident in incidents:
            episode_id = str(incident["episode_id"])
            if str(incident["status"]) in TERMINAL_STATUSES:
                skipped_terminal += 1
                continue

            plan = plans.get(episode_id)
            route = routes.get(episode_id, {})
            if not plan:
                continue

            assignees = {
                "REGADOR": (route.get("primaryAssignee") or {}).get("userId"),
                "SUPERVISOR": (route.get("supervisorAssignee") or {}).get("userId"),
                "COORDINADOR": (route.get("coordinatorAssignee") or {}).get("userId"),
            }

            for event in plan.get("timelinePreview", []):
                scheduled_at = str(event.get("at") or "")
                action = str(event.get("action") or "")
                for role in event.get("recipients", []):
                    role = str(role)
                    user_id = assignees.get(role)
                    if test_replay_mode:
                        status = "BLOCKED_TEST_REPLAY"
                    else:
                        status = "PENDING" if user_id else "BLOCKED_UNASSIGNED"
                    outbox_id = _outbox_id(episode_id, action, role, scheduled_at)
                    payload = {
                        "episodeId": episode_id,
                        "action": action,
                        "recipientRole": role,
                        "recipientUserId": user_id,
                        "scheduledAt": scheduled_at,
                        "channel": "WHATSAPP",
                        "deliveryMode": "TEST_REPLAY" if test_replay_mode else "PRODUCTION",
                    }

                    existing = connection.execute(
                        "SELECT status FROM notification_outbox WHERE outbox_id = ?",
                        (outbox_id,),
                    ).fetchone()
                    if existing is None:
                        connection.execute(
                            """
                            INSERT INTO notification_outbox (
                                outbox_id, episode_id, channel, action,
                                recipient_role, recipient_user_id, scheduled_at,
                                status, attempt_count, payload_json,
                                created_at, updated_at
                            )
                            VALUES (?, ?, 'WHATSAPP', ?, ?, ?, ?, ?, 0, ?, ?, ?)
                            """,
                            (
                                outbox_id,
                                episode_id,
                                action,
                                role,
                                user_id,
                                scheduled_at,
                                status,
                                json.dumps(payload, ensure_ascii=False),
                                now,
                                now,
                            ),
                        )
                        inserted += 1
                    elif str(existing["status"]) not in {"SENT", "CANCELLED"}:
                        connection.execute(
                            """
                            UPDATE notification_outbox
                            SET recipient_user_id = ?, status = ?,
                                payload_json = ?, updated_at = ?
                            WHERE outbox_id = ?
                            """,
                            (
                                user_id,
                                status,
                                json.dumps(payload, ensure_ascii=False),
                                now,
                                outbox_id,
                            ),
                        )
                        updated += 1

                    if status == "PENDING":
                        pending += 1
                    else:
                        blocked += 1
                        if status == "BLOCKED_TEST_REPLAY":
                            blocked_test_replay += 1
                        elif status == "BLOCKED_UNASSIGNED":
                            blocked_unassigned += 1

        connection.commit()
        total = int(
            connection.execute(
                "SELECT COUNT(*) AS n FROM notification_outbox"
            ).fetchone()["n"]
        )

    return {
        "success": True,
        "backend": "sqlite",
        "insertedOutboxItems": inserted,
        "updatedOutboxItems": updated,
        "pendingRecipientItems": pending,
        "blockedItems": blocked,
        "blockedTestReplayItems": blocked_test_replay,
        "blockedUnassignedItems": blocked_unassigned,
        "terminalIncidentsSkipped": skipped_terminal,
        "storedOutboxItemCount": total,
        "idempotent": True,
        "deliveryMode": "TEST_REPLAY" if test_replay_mode else "PRODUCTION",
        "sendsWhatsApp": False,
    }


def notification_outbox_summary(project_root: Path) -> dict[str, Any]:
    config = load_config(project_root)
    db_path = _store_path(project_root, config)
    if not db_path.exists():
        return {"success": False, "error": "Incident store does not exist."}

    with _connect(db_path) as connection:
        _init_lifecycle_schema(connection)
        rows = [
            dict(row)
            for row in connection.execute(
                """
                SELECT outbox_id, episode_id, channel, action, recipient_role,
                       recipient_user_id, scheduled_at, status, attempt_count
                FROM notification_outbox
                ORDER BY scheduled_at, episode_id, recipient_role
                """
            ).fetchall()
        ]
        evidence_count = int(
            connection.execute(
                "SELECT COUNT(*) AS n FROM incident_evidence"
            ).fetchone()["n"]
        )

    by_status = Counter(str(row["status"]) for row in rows)
    by_role = Counter(str(row["recipient_role"]) for row in rows)
    return {
        "success": True,
        "outboxItemCount": len(rows),
        "evidenceCount": evidence_count,
        "byStatus": dict(sorted(by_status.items())),
        "byRecipientRole": dict(sorted(by_role.items())),
        "preview": rows[:20],
        "realSendingEnabled": False,
    }
