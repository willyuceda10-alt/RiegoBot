from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .config import load_config
from .incident_store import _connect, _init_schema, _store_path


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _delivery_mode(config: dict[str, Any]) -> str:
    central = config.get("azureCentral") or {}
    operational = config.get("operationalState") or {}
    requested = str(central.get("deliveryMode") or "TEST_REPLAY").upper()

    if bool(operational.get("allowStaleForTesting", False)):
        return "TEST_REPLAY"
    if requested not in {"TEST_REPLAY", "PRODUCTION"}:
        return "TEST_REPLAY"
    return requested


def _batch_id(
    site_id: str,
    collector_id: str,
    delivery_mode: str,
    incidents: list[dict[str, Any]],
) -> str:
    parts = [site_id, collector_id, delivery_mode]
    for incident in sorted(incidents, key=lambda row: str(row["episodeId"])):
        parts.extend(
            [
                str(incident["episodeId"]),
                str(incident["lastSignalAt"]),
                str(incident["signalCount"]),
                str(incident["requiresPhotoEvidence"]),
                str(incident["requiresObservation"]),
                str(incident["requiresResolutionValidation"]),
            ]
        )
    digest = hashlib.sha1("|".join(parts).encode("utf-8")).hexdigest()[:16].upper()
    return f"BATCH-{digest}"


def build_central_batch_preview(project_root: Path) -> dict[str, Any]:
    config = load_config(project_root)
    db_path = _store_path(project_root, config)
    if not db_path.exists():
        return {
            "success": False,
            "error": "Incident store does not exist. Run incident-sync-candidate first.",
        }

    site = config.get("collector") or {}
    site_id = str(site.get("siteId") or "SITE01")
    collector_id = str(site.get("collectorId") or "COLLECTOR-LOCAL-01")
    delivery_mode = _delivery_mode(config)

    with _connect(db_path) as connection:
        _init_schema(connection)
        rows = connection.execute(
            """
            SELECT episode_id, romeo_id, fundo_id, incident_type, severity,
                   program_candidate_id, object_candidate_id,
                   first_detected_at, last_signal_at, signal_count,
                   requires_photo_evidence, requires_observation,
                   requires_resolution_validation, mapping_status
            FROM incidents
            ORDER BY first_detected_at, episode_id
            """
        ).fetchall()

    incidents = []
    for row in rows:
        incidents.append(
            {
                "episodeId": str(row["episode_id"]),
                "romeoId": str(row["romeo_id"]),
                "fundoId": row["fundo_id"],
                "incidentType": str(row["incident_type"]),
                "severity": str(row["severity"]),
                "firstDetectedAt": str(row["first_detected_at"]),
                "lastSignalAt": str(row["last_signal_at"]),
                "signalCount": int(row["signal_count"]),
                "programCandidateId": row["program_candidate_id"],
                "objectCandidateId": row["object_candidate_id"],
                "requiresPhotoEvidence": bool(row["requires_photo_evidence"]),
                "requiresObservation": bool(row["requires_observation"]),
                "requiresResolutionValidation": bool(
                    row["requires_resolution_validation"]
                ),
                "sourcePayload": {
                    "mappingStatus": row["mapping_status"],
                    "source": "DREAMREADER_LOCAL_STORE",
                    "deliveryMode": delivery_mode,
                },
            }
        )

    batch_id = _batch_id(site_id, collector_id, delivery_mode, incidents)
    payload = {
        "batchId": batch_id,
        "siteId": site_id,
        "collectorId": collector_id,
        "collectedAt": _utc_now(),
        "deliveryMode": delivery_mode,
        "incidents": incidents,
    }

    output = project_root / "runtime" / "central_batch_preview.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    temp = output.with_suffix(".tmp")
    temp.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    temp.replace(output)

    central = config.get("azureCentral") or {}
    return {
        "success": True,
        "batchId": batch_id,
        "siteId": site_id,
        "collectorId": collector_id,
        "deliveryMode": delivery_mode,
        "incidentCount": len(incidents),
        "outputFile": str(output),
        "apiBaseUrl": str(central.get("apiBaseUrl") or ""),
        "pushEnabled": bool(central.get("enabled", False)),
        "safeNote": (
            "This command only prepares the central payload. It does not send data. "
            "Stale/testing evidence is forced to TEST_REPLAY."
        ),
    }
