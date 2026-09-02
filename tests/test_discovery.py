from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from dreamreader.discovery import discover_dreams, get_discovery_info


class DiscoveryTests(unittest.TestCase):
    def _config(self, root: str) -> dict:
        return {
            "collector": {"collectorId": "COLLECTOR-TEST", "siteId": "SITE99"},
            "discovery": {"rootPath": root, "dreamPattern": "Dream*_1.mdb"},
            "dreams": [
                {"dreamId": "11", "name": "Configured 11", "enabled": True},
                {"dreamId": "13", "name": "Disabled 13", "enabled": False},
            ],
        }

    def test_new_dream_is_discovered_without_code_change(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "Dream11_1.mdb").touch()
            (root / "Dream13_1.mdb").touch()
            (root / "Dream21_1.mdb").touch()

            rows = discover_dreams(root, self._config("."))
            by_id = {row["dreamId"]: row for row in rows}

            self.assertEqual(by_id["11"]["status"], "CONFIGURED")
            self.assertEqual(by_id["13"]["status"], "DISABLED")
            self.assertEqual(by_id["21"]["status"], "DISCOVERED")
            self.assertEqual(by_id["21"]["dreamKey"], "SITE99-DREAM-21")

    def test_auto_detects_sibling_dream_realtime_folder(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            project = base / "RiegoBot"
            project.mkdir()
            dream = base / "Dream_Realtime" / "Dream"
            dream.mkdir(parents=True)
            (dream / "Dream17_1.mdb").touch()

            with patch.dict(os.environ, {}, clear=False):
                os.environ.pop("RIEGOBOT_DREAM_ROOT", None)
                info = get_discovery_info(project, self._config("../Dream"))

            self.assertEqual(
                info["source"],
                "auto:sibling/Dream_Realtime/Dream",
            )
            self.assertEqual(info["matchingFileCount"], 1)
            self.assertEqual(info["matchingFiles"], ["Dream17_1.mdb"])

    def test_environment_override_has_priority_when_it_contains_dreams(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            project = base / "RiegoBot"
            project.mkdir()
            override = base / "ExternalDream"
            override.mkdir()
            (override / "Dream25_1.mdb").touch()

            with patch.dict(
                os.environ,
                {"RIEGOBOT_DREAM_ROOT": str(override)},
                clear=False,
            ):
                info = get_discovery_info(project, self._config("../Dream"))

            self.assertEqual(info["source"], "environment")
            self.assertEqual(info["matchingFiles"], ["Dream25_1.mdb"])


if __name__ == "__main__":
    unittest.main()
