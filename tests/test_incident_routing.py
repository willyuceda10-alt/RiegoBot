from __future__ import annotations

import unittest

from dreamreader.routing import route_episode


class IncidentRoutingTests(unittest.TestCase):
    def setUp(self) -> None:
        self.episode = {
            "episodeId": "EPI-1",
            "romeoId": "11",
            "incidentType": "HIGH_FLOW",
            "severity": "HIGH",
            "firstDetectedAt": "2026-09-02T10:00:00",
        }

    def test_unassigned_without_configuration(self) -> None:
        route = route_episode(self.episode, [], [])
        self.assertEqual(route["routingStatus"], "UNASSIGNED")
        self.assertIn("REGADOR", route["missingRoles"])
        self.assertFalse(route["canSendInitialWhatsApp"])

    def test_routes_by_romeo_role_and_priority(self) -> None:
        users = [
            {"userId": "R1", "displayName": "Regador A", "enabled": True, "whatsappNumber": "+51000000001"},
            {"userId": "R2", "displayName": "Regador B", "enabled": True, "whatsappNumber": "+51000000002"},
            {"userId": "S1", "displayName": "Supervisor A", "enabled": True, "whatsappNumber": "+51000000003"},
            {"userId": "C1", "displayName": "Coordinador A", "enabled": True, "whatsappNumber": "+51000000004"},
        ]
        assignments = [
            {"assignmentId": "A1", "userId": "R1", "role": "REGADOR", "romeoIds": ["11"], "priority": 1},
            {"assignmentId": "A2", "userId": "R2", "role": "REGADOR", "romeoIds": ["11"], "priority": 10},
            {"assignmentId": "A3", "userId": "S1", "role": "SUPERVISOR", "romeoIds": ["11"], "priority": 1},
            {"assignmentId": "A4", "userId": "C1", "role": "COORDINADOR", "romeoIds": ["*"], "priority": 1},
        ]

        route = route_episode(self.episode, users, assignments)

        self.assertEqual(route["routingStatus"], "ROUTED")
        self.assertEqual(route["primaryAssignee"]["userId"], "R2")
        self.assertEqual(route["supervisorAssignee"]["userId"], "S1")
        self.assertEqual(route["coordinatorAssignee"]["userId"], "C1")
        self.assertTrue(route["canSendInitialWhatsApp"])

    def test_shift_filter_can_leave_episode_unassigned(self) -> None:
        users = [
            {"userId": "R1", "displayName": "Regador A", "enabled": True, "whatsappNumber": "+51000000001"},
        ]
        assignments = [
            {
                "assignmentId": "A1",
                "userId": "R1",
                "role": "REGADOR",
                "romeoIds": ["11"],
                "priority": 1,
                "shift": {"days": [2], "startTime": "18:00", "endTime": "23:00"},
            }
        ]

        route = route_episode(self.episode, users, assignments)
        self.assertEqual(route["routingStatus"], "UNASSIGNED")


if __name__ == "__main__":
    unittest.main()
