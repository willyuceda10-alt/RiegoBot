from __future__ import annotations

import unittest

from dreamreader.central_sync import _batch_id, _delivery_mode


class CentralSyncTests(unittest.TestCase):
    def test_stale_testing_forces_test_replay(self) -> None:
        config = {
            "operationalState": {"allowStaleForTesting": True},
            "azureCentral": {"deliveryMode": "PRODUCTION"},
        }
        self.assertEqual(_delivery_mode(config), "TEST_REPLAY")

    def test_production_mode_requires_testing_disabled(self) -> None:
        config = {
            "operationalState": {"allowStaleForTesting": False},
            "azureCentral": {"deliveryMode": "PRODUCTION"},
        }
        self.assertEqual(_delivery_mode(config), "PRODUCTION")

    def test_batch_id_is_deterministic(self) -> None:
        incidents = [
            {
                "episodeId": "EPI-2",
                "lastSignalAt": "2026-09-02T10:00:00",
                "signalCount": 2,
                "requiresPhotoEvidence": False,
                "requiresObservation": True,
                "requiresResolutionValidation": True,
            },
            {
                "episodeId": "EPI-1",
                "lastSignalAt": "2026-09-02T09:00:00",
                "signalCount": 1,
                "requiresPhotoEvidence": True,
                "requiresObservation": True,
                "requiresResolutionValidation": True,
            },
        ]
        a = _batch_id("SITE01", "COLLECTOR-1", "TEST_REPLAY", incidents)
        b = _batch_id("SITE01", "COLLECTOR-1", "TEST_REPLAY", list(reversed(incidents)))
        self.assertEqual(a, b)


if __name__ == "__main__":
    unittest.main()
