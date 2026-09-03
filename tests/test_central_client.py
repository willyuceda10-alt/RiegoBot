from __future__ import annotations

import unittest
from pathlib import Path
from unittest.mock import patch

from dreamreader.central_client import push_central_batch


class CentralClientTests(unittest.TestCase):
    def test_push_is_blocked_when_central_is_disabled(self) -> None:
        config = {
            "azureCentral": {
                "enabled": False,
            }
        }
        with patch("dreamreader.central_client.load_config", return_value=config):
            result = push_central_batch(Path("."))

        self.assertFalse(result["success"])
        self.assertTrue(result["blocked"])
        self.assertEqual(result["reason"], "AZURE_CENTRAL_DISABLED")

    def test_https_is_required_for_non_local_endpoint(self) -> None:
        config = {
            "azureCentral": {
                "enabled": True,
                "apiBaseUrl": "http://example.invalid",
                "allowHttpLocalhost": True,
            }
        }
        with patch("dreamreader.central_client.load_config", return_value=config):
            result = push_central_batch(Path("."))

        self.assertFalse(result["success"])
        self.assertEqual(result["reason"], "HTTPS_REQUIRED")

    def test_api_key_is_required_before_building_payload(self) -> None:
        config = {
            "azureCentral": {
                "enabled": True,
                "apiBaseUrl": "https://riegobot.example",
                "apiKeyEnvironmentVariable": "RIEGOBOT_TEST_KEY_MISSING",
            }
        }
        with (
            patch("dreamreader.central_client.load_config", return_value=config),
            patch.dict("os.environ", {}, clear=True),
        ):
            result = push_central_batch(Path("."))

        self.assertFalse(result["success"])
        self.assertEqual(result["reason"], "COLLECTOR_API_KEY_MISSING")


if __name__ == "__main__":
    unittest.main()
