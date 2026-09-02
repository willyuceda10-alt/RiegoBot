from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from dreamreader.discovery import discover_dreams


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


if __name__ == "__main__":
    unittest.main()
