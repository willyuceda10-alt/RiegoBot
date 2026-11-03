from __future__ import annotations

import unittest

from dreamreader.session import build_session_id


class SessionIdTests(unittest.TestCase):
    def test_session_ids_are_unique(self) -> None:
        values = [build_session_id() for _ in range(500)]
        self.assertEqual(len(values), len(set(values)))

    def test_session_id_contains_no_spaces(self) -> None:
        value = build_session_id()
        self.assertNotIn(" ", value)


if __name__ == "__main__":
    unittest.main()
