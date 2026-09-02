from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from dreamreader.bridge import invoke_readonly_bridge


class BridgeTests(unittest.TestCase):
    def test_missing_powershell_is_reported_without_execution(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            with patch("dreamreader.bridge._find_powershell", return_value=None):
                result = invoke_readonly_bridge(root)

            self.assertFalse(result.success)
            self.assertEqual(result.exit_code, 127)
            self.assertEqual(result.command, [])

    def test_bridge_command_uses_existing_readonly_entrypoint(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            scripts = root / "scripts"
            scripts.mkdir()
            (scripts / "INICIAR_V1_3.ps1").write_text("# test", encoding="utf-8")

            fake_completed = type(
                "Completed",
                (),
                {"returncode": 0, "stdout": "OK", "stderr": ""},
            )()

            with (
                patch(
                    "dreamreader.bridge._find_powershell",
                    return_value=r"C:\\Windows\\System32\\WindowsPowerShell\\v1.0\\powershell.exe",
                ),
                patch("dreamreader.bridge.subprocess.run", return_value=fake_completed) as run,
            ):
                result = invoke_readonly_bridge(root, "NORMALIZED")

            self.assertTrue(result.success)
            args = run.call_args.args[0]
            self.assertIn("-NoProfile", args)
            self.assertIn("-File", args)
            self.assertIn("NORMALIZED", args)
            self.assertNotIn("cmd.exe", args)


if __name__ == "__main__":
    unittest.main()
