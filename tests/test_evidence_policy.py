from __future__ import annotations

import unittest
from pathlib import Path
from unittest.mock import patch

from dreamreader.evidence_policy import resolve_evidence_policy


class IncidentEvidencePolicyTests(unittest.TestCase):
    def test_photo_is_optional_by_default(self) -> None:
        config = {
            "incidentEvidencePolicies": {
                "policySource": "LOCAL_CONFIG_UNTIL_AZURE",
                "default": {
                    "requiresPhotoEvidence": False,
                    "requiresObservation": True,
                    "requiresResolutionValidation": True,
                },
                "byIncidentType": {},
            }
        }
        with patch("dreamreader.evidence_policy.load_config", return_value=config):
            policy = resolve_evidence_policy(Path("."), "HIGH_FLOW")

        self.assertFalse(policy["requiresPhotoEvidence"])
        self.assertTrue(policy["requiresObservation"])
        self.assertTrue(policy["requiresResolutionValidation"])

    def test_photo_can_be_required_for_selected_incident_type(self) -> None:
        config = {
            "incidentEvidencePolicies": {
                "policySource": "LOCAL_CONFIG_UNTIL_AZURE",
                "default": {
                    "requiresPhotoEvidence": False,
                    "requiresObservation": True,
                    "requiresResolutionValidation": True,
                },
                "byIncidentType": {
                    "RTU_COMMUNICATION_ERROR": {
                        "requiresPhotoEvidence": True
                    }
                },
            }
        }
        with patch("dreamreader.evidence_policy.load_config", return_value=config):
            policy = resolve_evidence_policy(Path("."), "RTU_COMMUNICATION_ERROR")

        self.assertTrue(policy["requiresPhotoEvidence"])
        self.assertEqual(policy["policySource"], "LOCAL_CONFIG_UNTIL_AZURE")


if __name__ == "__main__":
    unittest.main()
