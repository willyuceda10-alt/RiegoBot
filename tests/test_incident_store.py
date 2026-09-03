from __future__ import annotations

import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from dreamreader.incident_store import incident_store_summary, sync_incident_store_candidate


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

ROUTE = {
    "episodeId": "EPI-TEST-1",
    "routingStatus": "ROUTED",
    "primaryAssignee": {"userId": "R1"},
    "supervisorAssignee": {"userId": "S1"},
    "coordinatorAssignee": {"userId": "C1"},
}

PLAN = {
    "episodeId": "EPI-TEST-1",
    "responseDueAt": "2026-09-02T10:10:00",
    "supervisorEscalationAt": "2026-09-02T10:30:00",
    "coordinatorEscalationAt": "2026-09-02T10:45:00",
}


class IncidentStoreTests(unittest.TestCase):
    def _config(self) -> dict:
        return {
            "incidentPersistence": {
                "backend": "sqlite",
                "path": "runtime/test_incident_state.db",
            }
        }

    def _patches(self):
        return (
            patch(
                "dreamreader.incident_store.build_incident_episodes",
                return_value={"success": True, "episodeCount": 1, "episodes": [EPISODE]},
            ),
            patch(
                "dreamreader.incident_store.build_incident_routing_candidate",
                return_value={"success": True, "routes": [ROUTE]},
            ),
            patch(
                "dreamreader.incident_store.build_incident_sla_plan",
                return_value={"success": True, "plans": [PLAN]},
            ),
            patch(
                "dreamreader.incident_store.load_config",
                return_value=self._config(),
            ),
        )

    def test_sync_is_idempotent(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            patches = self._patches()
            with patches[0], patches[1], patches[2], patches[3]:
                first = sync_incident_store_candidate(root)
                second = sync_incident_store_candidate(root)
                summary = incident_store_summary(root)

            self.assertEqual(first["insertedIncidents"], 1)
            self.assertEqual(first["storedEventCount"], 1)
            self.assertEqual(second["insertedIncidents"], 0)
            self.assertEqual(second["updatedIncidents"], 1)
            self.assertEqual(second["storedIncidentCount"], 1)
            self.assertEqual(second["storedEventCount"], 1)
            self.assertEqual(summary["incidentCount"], 1)
            self.assertEqual(summary["eventCount"], 1)

    def test_sync_preserves_existing_workflow_status(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            patches = self._patches()
            with patches[0], patches[1], patches[2], patches[3]:
                sync_incident_store_candidate(root)

                db_path = root / "runtime" / "test_incident_state.db"
                with sqlite3.connect(db_path) as connection:
                    connection.execute(
                        "UPDATE incidents SET status='IN_PROGRESS' WHERE episode_id='EPI-TEST-1'"
                    )
                    connection.commit()

                second = sync_incident_store_candidate(root)
                summary = incident_store_summary(root)

            self.assertEqual(second["existingStatusesPreserved"], 1)
            self.assertEqual(summary["byStatus"], {"IN_PROGRESS": 1})
            self.assertEqual(summary["activeIncidentCount"], 1)


if __name__ == "__main__":
    unittest.main()
