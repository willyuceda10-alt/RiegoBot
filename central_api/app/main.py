from __future__ import annotations

from fastapi import FastAPI, HTTPException, Query
from psycopg.types.json import Jsonb

from .db import database_health, get_connection
from .schemas import CollectorBatchResult, CollectorIncidentBatch
from .settings import load_settings

app = FastAPI(
    title="RiegoBot Central API",
    version="2.0.0-alpha",
    description="Central ingestion and monitoring API for RiegoBot.",
)


@app.get("/health")
def health() -> dict[str, object]:
    settings = load_settings()
    return {
        "service": "RiegoBot Central API",
        "version": settings.version,
        "environment": settings.environment,
        "database": database_health(),
    }


@app.post(
    "/api/v1/collector/incident-batches",
    response_model=CollectorBatchResult,
)
def ingest_incident_batch(batch: CollectorIncidentBatch) -> CollectorBatchResult:
    settings = load_settings()
    if batch.deliveryMode == "TEST_REPLAY" and not settings.allow_test_replay:
        raise HTTPException(
            status_code=409,
            detail="TEST_REPLAY ingestion is disabled in this environment.",
        )

    with get_connection() as connection:
        with connection.transaction():
            connection.execute(
                """
                INSERT INTO sites (site_id, name)
                VALUES (%s, %s)
                ON CONFLICT (site_id) DO NOTHING
                """,
                (batch.siteId, batch.siteId),
            )
            connection.execute(
                """
                INSERT INTO collectors (collector_id, site_id, name, last_seen_at)
                VALUES (%s, %s, %s, now())
                ON CONFLICT (collector_id) DO UPDATE SET
                    site_id = EXCLUDED.site_id,
                    last_seen_at = now()
                """,
                (batch.collectorId, batch.siteId, batch.collectorId),
            )

            inserted_batch = connection.execute(
                """
                INSERT INTO collector_ingest_batches (
                    batch_id, site_id, collector_id, collected_at,
                    delivery_mode, incident_count
                )
                VALUES (%s, %s, %s, %s, %s, %s)
                ON CONFLICT (batch_id) DO NOTHING
                RETURNING batch_id
                """,
                (
                    batch.batchId,
                    batch.siteId,
                    batch.collectorId,
                    batch.collectedAt,
                    batch.deliveryMode,
                    len(batch.incidents),
                ),
            ).fetchone()

            if inserted_batch is None:
                stored = connection.execute(
                    """
                    SELECT incident_count, delivery_mode
                    FROM collector_ingest_batches
                    WHERE batch_id = %s
                    """,
                    (batch.batchId,),
                ).fetchone()
                return CollectorBatchResult(
                    success=True,
                    batchId=batch.batchId,
                    alreadyProcessed=True,
                    incidentCount=int(stored["incident_count"]),
                    insertedIncidents=0,
                    updatedIncidents=0,
                    deliveryMode=stored["delivery_mode"],
                )

            inserted = 0
            updated = 0
            for incident in batch.incidents:
                connection.execute(
                    """
                    INSERT INTO romeos (site_id, romeo_id, display_name, last_seen_at)
                    VALUES (%s, %s, %s, now())
                    ON CONFLICT (site_id, romeo_id) DO UPDATE SET
                        last_seen_at = now()
                    """,
                    (
                        batch.siteId,
                        incident.romeoId,
                        f"Romeo {incident.romeoId}",
                    ),
                )

                existing = connection.execute(
                    "SELECT 1 FROM incidents WHERE episode_id = %s",
                    (incident.episodeId,),
                ).fetchone()

                connection.execute(
                    """
                    INSERT INTO incidents (
                        episode_id, site_id, collector_id, romeo_id, fundo_id,
                        incident_type, severity, first_detected_at, last_signal_at,
                        signal_count, delivery_mode, requires_photo_evidence,
                        requires_observation, requires_resolution_validation,
                        source_payload, created_at, updated_at
                    )
                    VALUES (
                        %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                        %s, %s, %s, %s, now(), now()
                    )
                    ON CONFLICT (episode_id) DO UPDATE SET
                        collector_id = EXCLUDED.collector_id,
                        romeo_id = EXCLUDED.romeo_id,
                        fundo_id = EXCLUDED.fundo_id,
                        incident_type = EXCLUDED.incident_type,
                        severity = EXCLUDED.severity,
                        first_detected_at = EXCLUDED.first_detected_at,
                        last_signal_at = EXCLUDED.last_signal_at,
                        signal_count = EXCLUDED.signal_count,
                        delivery_mode = EXCLUDED.delivery_mode,
                        requires_photo_evidence = EXCLUDED.requires_photo_evidence,
                        requires_observation = EXCLUDED.requires_observation,
                        requires_resolution_validation = EXCLUDED.requires_resolution_validation,
                        source_payload = EXCLUDED.source_payload,
                        updated_at = now()
                    """,
                    (
                        incident.episodeId,
                        batch.siteId,
                        batch.collectorId,
                        incident.romeoId,
                        incident.fundoId,
                        incident.incidentType,
                        incident.severity,
                        incident.firstDetectedAt,
                        incident.lastSignalAt,
                        incident.signalCount,
                        batch.deliveryMode,
                        incident.requiresPhotoEvidence,
                        incident.requiresObservation,
                        incident.requiresResolutionValidation,
                        Jsonb(incident.sourcePayload),
                    ),
                )

                if existing is None:
                    inserted += 1
                    connection.execute(
                        """
                        INSERT INTO incident_events (
                            episode_id, event_type, to_status, actor_type,
                            occurred_at, metadata
                        )
                        VALUES (%s, 'INCIDENT_CREATED', 'DETECTED', 'COLLECTOR', now(), %s)
                        """,
                        (
                            incident.episodeId,
                            Jsonb({
                                "collectorId": batch.collectorId,
                                "batchId": batch.batchId,
                                "deliveryMode": batch.deliveryMode,
                            }),
                        ),
                    )
                else:
                    updated += 1

    return CollectorBatchResult(
        success=True,
        batchId=batch.batchId,
        alreadyProcessed=False,
        incidentCount=len(batch.incidents),
        insertedIncidents=inserted,
        updatedIncidents=updated,
        deliveryMode=batch.deliveryMode,
    )


@app.get("/api/v1/incidents")
def list_incidents(
    status: str | None = Query(default=None),
    romeo_id: str | None = Query(default=None, alias="romeoId"),
    limit: int = Query(default=100, ge=1, le=1000),
) -> dict[str, object]:
    where = []
    params: list[object] = []

    if status:
        where.append("status = %s")
        params.append(status.upper())
    if romeo_id:
        where.append("romeo_id = %s")
        params.append(romeo_id)

    sql = """
        SELECT episode_id, site_id, collector_id, romeo_id, fundo_id,
               incident_type, severity, first_detected_at, last_signal_at,
               signal_count, status, delivery_mode, primary_user_id,
               supervisor_user_id, coordinator_user_id,
               requires_photo_evidence, requires_observation,
               requires_resolution_validation, updated_at
        FROM incidents
    """
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += " ORDER BY first_detected_at DESC LIMIT %s"
    params.append(limit)

    with get_connection() as connection:
        rows = connection.execute(sql, params).fetchall()

    return {"success": True, "count": len(rows), "incidents": rows}


@app.get("/api/v1/incidents/{episode_id}")
def get_incident(episode_id: str) -> dict[str, object]:
    with get_connection() as connection:
        incident = connection.execute(
            "SELECT * FROM incidents WHERE episode_id = %s",
            (episode_id,),
        ).fetchone()
        if incident is None:
            raise HTTPException(status_code=404, detail="Incident not found.")

        events = connection.execute(
            """
            SELECT event_id, event_type, from_status, to_status, actor_type,
                   actor_id, occurred_at, observation, metadata
            FROM incident_events
            WHERE episode_id = %s
            ORDER BY occurred_at, event_id
            """,
            (episode_id,),
        ).fetchall()

    return {"success": True, "incident": incident, "events": events}


@app.get("/api/v1/kpis/incidents")
def incident_kpis() -> dict[str, object]:
    with get_connection() as connection:
        summary = connection.execute(
            """
            SELECT
                COUNT(*) AS total,
                COUNT(*) FILTER (
                    WHERE status NOT IN ('RESOLVED', 'CLOSED')
                ) AS active,
                COUNT(*) FILTER (
                    WHERE status IN ('RESOLVED', 'CLOSED')
                ) AS resolved,
                COUNT(*) FILTER (
                    WHERE routing_status = 'UNASSIGNED'
                ) AS unassigned,
                COUNT(*) FILTER (
                    WHERE severity = 'CRITICAL'
                    AND status NOT IN ('RESOLVED', 'CLOSED')
                ) AS critical_active
            FROM incidents
            """
        ).fetchone()

        by_type = connection.execute(
            """
            SELECT incident_type, COUNT(*) AS incident_count
            FROM incidents
            GROUP BY incident_type
            ORDER BY incident_count DESC, incident_type
            """
        ).fetchall()

    return {
        "success": True,
        "summary": summary,
        "byType": by_type,
    }
