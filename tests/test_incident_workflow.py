from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from dreamreader.incident_workflow import build_sla_timeline
from dreamreader.incidents import build_incident_candidates


class IncidentWorkflowTests(unittest.TestCase):
    def test_exact_duplicate_report_rows_are_dropped(self) -> None:
        row = {
            "RomeoId": "11",
            "Timestamp": "2026-09-02T14:23:17",
            "ReportCodeRaw": 33,
            "ReportTextRaw": "Caudal Alta %",
            "ReportFailRaw": True,
            "ReportId1Raw": 21,
            "ReportId2Raw": 302,
            "ReportId2NameRaw": "46",
        }

        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            normalized = root / "output" / "SITE01" / "COLLECTOR" / "SESSION" / "normalized"
            normalized.mkdir(parents=True)
            (normalized / "reports_history_candidate.json").write_text(
                json.dumps([row, row]),
                encoding="utf-8",
            )

            payload = build_incident_candidates(root)

        self.assertTrue(payload["success"])
        self.assertEqual(payload["sourceRowCount"], 2)
        self.assertEqual(payload["duplicateSignalRowsDropped"], 1)
        self.assertEqual(payload["incidentCount"], 1)

    def test_sla_timeline_does_not_duplicate_supervisor_notification(self) -> None:
        timeline = build_sla_timeline(
            detected="2026-09-02T10:00:00",
            response_due=10,
            cadence=10,
            supervisor_after=30,
            coordinator_after=45,
            preview_count=5,
        )

        at_30 = [item for item in timeline if item["offsetMinutes"] == 30]
        self.assertEqual(len(at_30), 1)
        self.assertEqual(at_30[0]["action"], "REMINDER_3")
        self.assertEqual(at_30[0]["recipients"], ["REGADOR", "SUPERVISOR"])

        at_45 = [item for item in timeline if item["offsetMinutes"] == 45]
        self.assertEqual(len(at_45), 1)
        self.assertEqual(at_45[0]["action"], "ESCALATE_COORDINATOR")
        self.assertEqual(
            at_45[0]["recipients"],
            ["REGADOR", "SUPERVISOR", "COORDINADOR"],
        )

    def test_first_reminder_matches_response_due_without_duplicate_due_event(self) -> None:
        timeline = build_sla_timeline(
            detected="2026-09-02T10:00:00",
            response_due=10,
            cadence=10,
            supervisor_after=30,
            coordinator_after=45,
            preview_count=2,
        )

        at_10 = [item for item in timeline if item["offsetMinutes"] == 10]
        self.assertEqual(len(at_10), 1)
        self.assertEqual(at_10[0]["action"], "REMINDER_1")


if __name__ == "__main__":
    unittest.main()
