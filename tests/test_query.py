from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from dreamreader.query import _parse_timestamp, build_romeo_query, find_latest_valid_session


class QueryTests(unittest.TestCase):
    def _write_session(self, root: Path, name: str, *, errors=None, dreams=3, mtime=None) -> Path:
        session = root / "output" / "SITE01" / "COLLECTOR" / name
        normalized = session / "normalized"
        normalized.mkdir(parents=True)
        (session / "session.json").write_text(
            json.dumps({"SessionId": name, "EndTime": "2026-09-02T14:00:00-05:00", "Errors": errors or [], "DreamsDiscovered": dreams}),
            encoding="utf-8",
        )
        return session

    def test_latest_valid_session_ignores_error_sessions(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            valid = self._write_session(root, "valid")
            invalid = self._write_session(root, "invalid", errors=["boom"])
            invalid.touch()
            self.assertEqual(find_latest_valid_session(root), valid)

    def test_build_romeo_query_filters_snapshot(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            session = self._write_session(root, "session")
            rows = [
                {"RomeoId": "11", "RomeoKey": "SITE01-DREAM-11", "MeterId": "22:1", "FlowRawValue": 10, "FlowUnitStatus": "UNRESOLVED"},
                {"RomeoId": "13", "RomeoKey": "SITE01-DREAM-13", "MeterId": "22:2", "FlowRawValue": 20, "FlowUnitStatus": "UNRESOLVED"},
            ]
            (session / "normalized" / "romeo_snapshot.json").write_text(json.dumps(rows), encoding="utf-8")
            payload = build_romeo_query(root, "13")
            self.assertTrue(payload["success"])
            self.assertEqual(payload["meterCount"], 1)
            self.assertEqual(payload["meters"][0]["MeterId"], "22:2")

    def test_naive_dream_timestamp_uses_site_timezone(self) -> None:
        parsed = _parse_timestamp("2026-08-26T12:21:01.0000000", "America/Lima")
        self.assertIsNotNone(parsed)
        self.assertEqual(parsed.utcoffset().total_seconds(), -5 * 3600)
        self.assertEqual(parsed.isoformat(), "2026-08-26T12:21:01-05:00")


if __name__ == "__main__":
    unittest.main()
