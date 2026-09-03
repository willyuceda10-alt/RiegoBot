from __future__ import annotations

import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from dreamreader.incident_lifecycle import (
    acknowledge_incident,
    add_incident_evidence,
    lifecycle_contract,
    sync_notification_outbox_candidate,
    transition_incident,
)
from dreamreader.incident_store import sync_incident_store_candidate


EPISODE = {
    "episodeId": "EPI-TEST-1",
    "romeoId": "11",
    "incidentType": "HIGH_FLOW",
    "severity": "HIGH",
    "programCandidateId": "21",
    "objectCandidateId": "46",
    "firstDetectedAt": "2026-09-02T10:00:00",
    "lastSignalAt": "2026-09-02T10:05:00",
    "signalCount": 2,
    "status": "DETECTED",
    "requiresPhotoEvidence": True,
    "requiresObservation": True,
    "requiresResolutionValidation": True,
    "mappingStatus": "CANDIDATE",
}

ROUTE_UNASSIGNED = {
    "episodeId": "EPI-TEST-1",
    "routingStatus": "UNASSIGNED",
    "primaryAssignee": None,
    "supervisorAssignee": None,
    "coordinatorAssignee": None,
}

PLAN = {
    "episodeId": "EPI-TEST-1",
    "responseDueAt": "2026-09-02T10:10:00",
    "supervisorEscalationAt": "2026-09-02T10:30:00",
    "coordinatorEscalationAt": "2026-09-02T10:45:00",
    "timelinePreview": [
        {
            "offsetMinutes": 0,
            "at": "2026-09-02T10:00:00",
            "action": "SEND_INITIAL_ALERT",
            "recipients": ["REGADOR"],
        },
        {
            "offsetMinutes": 10,
            "at": "2026-09-02T10:10:00",
            "action": "REMINDER_1",
            "recipients": ["REGADOR"],
        },
        {
            "offsetMinutes": 30,
            "at": "2026-09-02T10:30:00",
            "action": "REMINDER_3",
            "recipients": ["REGADOR", "SUPERVISOR"],
        },
    ],
}


class IncidentLifecycleTests(unittest.TestCase):
    def _config(self) -> dict:
        return {
            "incidentPersistence": {
                "backend": "sqlite",
                "path": "runtime/test_incident_state.db",
            }
        }

    def _sync_store(self, root: Path) -> None:
        with (
            patch(
                "dreamreader.incident_store.build_incident_episodes",
                return_value={"success": True, "episodeCount": 1, "episodes": [EPISODE]},
            ),
            patch(
                "dreamreader.incident_store.build_incident_routing_candidate",
                return_value={"success": True, "routes": [ROUTE_UNASSIGNED]},
            ),
            patch(
                "dreamreader.incident_store.build_incident_sla_plan",
                return_value={"success": True, "plans": [PLAN]},
            ),
            patch(
                "dreamreader.incident_store.load_config",
                return_value=self._config(),
            ),
        ):
            sync_incident_store_candidate(root)

    def test_acknowledgement_moves_to_in_progress_but_does_not_close(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self._sync_store(root)
            with patch(
                "dreamreader.incident_lifecycle.load_config",
                return_value=self._config(),
            ):
                result = acknowledge_incident(
                    root,
                    "EPI-TEST-1",
                    actor_id="REGADOR-1",
                    observation="Ya estoy revisando",
                )

            self.assertTrue(result["success"])
            self.assertEqual(result["toStatus"], "IN_PROGRESS")

    def test_pending_validation_requires_observation_and_photo(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self._sync_store(root)
            with patch(
                "dreamreader.incident_lifecycle.load_config",
                return_value=self._config(),
            ):
                acknowledge_incident(root, "EPI-TEST-1", actor_id="R1")
                blocked = transition_incident(
                    root,
                    "EPI-TEST-1",
                    "PENDING_VALIDATION",
                    actor_type="USER",
                    actor_id="R1",
                )
                self.assertFalse(blocked["success"])
                self.assertIn("observation", blocked["missingRequirements"])
                self.assertIn("photoEvidence", blocked["missingRequirements"])

                add_incident_evidence(
                    root,
                    "EPI-TEST-1",
                    evidence_type="PHOTO",
                    storage_ref="blob://candidate/photo-1",
                    file_name="foto.jpg",
                    mime_type="image/jpeg",
                    actor_id="R1",
                )
                allowed = transition_incident(
                    root,
                    "EPI-TEST-1",
                    "PENDING_VALIDATION",
                    actor_type="USER",
                    actor_id="R1",
                    observation="Caudal normalizado, revisar cierre.",
                )
                self.assertTrue(allowed["success"])

    def test_outbox_is_blocked_and_idempotent_without_assignments(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self._sync_store(root)
            with (
                patch(
                    "dreamreader.incident_lifecycle.load_config",
                    return_value=self._config(),
                ),
                patch(
                    "dreamreader.incident_lifecycle.build_incident_sla_plan",
                    return_value={"success": True, "plans": [PLAN]},
                ),
                patch(
                    "dreamreader.incident_lifecycle.build_incident_routing_candidate",
                    return_value={"success": True, "routes": [ROUTE_UNASSIGNED]},
                ),
            ):
                first = sync_notification_outbox_candidate(root)
                second = sync_notification_outbox_candidate(root)

            self.assertEqual(first["insertedOutboxItems"], 4)
            self.assertEqual(first["blockedUnassignedItems"], 4)
            self.assertEqual(second["insertedOutboxItems"], 0)
            self.assertEqual(second["storedOutboxItemCount"], 4)

    def test_contract_encodes_reminder_semantics(self) -> None:
        contract = lifecycle_contract()
        self.assertFalse(contract["whatsappSemantics"]["acknowledgementClosesIncident"])
        self.assertFalse(contract["whatsappSemantics"]["inProgressStopsReminders"])
        self.assertTrue(contract["whatsappSemantics"]["resolvedOrClosedStopsReminders"])


if __name__ == "__main__":
    unittest.main()
