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

    def test_many_dreams_scale_without_hardcoded_ids(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            ids = ["11", "13", "17", "18", "21", "25", "30", "44", "101"]
            for dream_id in ids:
                (root / f"Dream{dream_id}_1.mdb").touch()

            rows = discover_dreams(root, self._config("."))
            by_id = {row["dreamId"]: row for row in rows}

            self.assertEqual(set(by_id), set(ids))
            self.assertEqual(by_id["11"]["status"], "CONFIGURED")
            self.assertEqual(by_id["13"]["status"], "DISABLED")
            for dream_id in {"17", "18", "21", "25", "30", "44", "101"}:
                self.assertEqual(by_id[dream_id]["status"], "DISCOVERED")
                self.assertEqual(by_id[dream_id]["dreamKey"], f"SITE99-DREAM-{dream_id}")

    def test_auto_detects_dream_two_ancestors_above_nested_zip(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            project = base / "outer" / "inner"
            project.mkdir(parents=True)
            dream = base / "Dream"
            dream.mkdir()
            (dream / "Dream17_1.mdb").touch()

            with patch.dict(os.environ, {}, clear=False):
                os.environ.pop("RIEGOBOT_DREAM_ROOT", None)
                info = get_discovery_info(project, self._config("../Dream"))

            self.assertEqual(info["source"], "auto:ancestor2/Dream")
            self.assertEqual(info["matchingFiles"], ["Dream17_1.mdb"])

    def test_environment_override_has_priority(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            project = base / "RiegoBot"
            project.mkdir()
            override = base / "ExternalDream"
            override.mkdir()
            (override / "Dream25_1.mdb").touch()

            with patch.dict(os.environ, {"RIEGOBOT_DREAM_ROOT": str(override)}, clear=False):
                info = get_discovery_info(project, self._config("../Dream"))

            self.assertEqual(info["source"], "environment")
            self.assertEqual(info["matchingFiles"], ["Dream25_1.mdb"])


if __name__ == "__main__":
    unittest.main()
