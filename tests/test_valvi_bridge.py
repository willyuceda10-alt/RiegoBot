import json
import subprocess
import unittest
from unittest.mock import Mock

from valvi.bridge import BridgeError, parse_probe, run_probe


def payload(**changes):
    result = dict(status="PROVIDERS_CHECKED", providers=["Microsoft.ACE.OLEDB.16.0"], process_bits=64,
                  fixture_checked=False, table_count=None, read_only=True)
    result.update(changes)
    return json.dumps(result)


class BridgeTests(unittest.TestCase):
    def test_provider_inventory(self):
        self.assertEqual(parse_probe(payload())["process_bits"], 64)

    def test_fixture_read(self):
        self.assertEqual(parse_probe(payload(status="FIXTURE_READ", fixture_checked=True, table_count=0))["table_count"], 0)

    def test_unreadable_fixture(self):
        self.assertEqual(parse_probe(payload(status="FIXTURE_UNREADABLE", fixture_checked=True))["status"], "FIXTURE_UNREADABLE")

    def test_invalid_payloads(self):
        for raw in ("not json", "[]", payload(read_only=False), payload(extra="private"),
                    payload(providers=["unknown"]), payload(providers=["Microsoft.ACE.OLEDB.16.0"] * 2),
                    payload(process_bits=16), payload(status=[]), payload(table_count=0),
                    payload(status="FIXTURE_READ", fixture_checked=True, table_count=True)):
            with self.subTest(raw=raw), self.assertRaises(BridgeError):
                parse_probe(raw)

    def test_runner_success(self):
        runner = Mock(return_value=subprocess.CompletedProcess([], 0, payload().encode("utf-8"), b""))
        self.assertEqual(run_probe(["local-test"], runner=runner)["status"], "PROVIDERS_CHECKED")
        self.assertEqual(runner.call_args.kwargs["timeout"], 30)
        self.assertFalse(runner.call_args.kwargs["text"])

    def test_runner_failure(self):
        runner = Mock(return_value=subprocess.CompletedProcess([], 1, b"", b"private error"))
        with self.assertRaises(BridgeError) as exc:
            run_probe(["local-test"], runner=runner)
        self.assertNotIn("private error", str(exc.exception))

    def test_timeout(self):
        with self.assertRaises(BridgeError):
            run_probe(["local-test"], runner=Mock(side_effect=subprocess.TimeoutExpired("local-test", 30)))

    def test_missing_process(self):
        with self.assertRaises(BridgeError):
            run_probe(["local-test"], runner=Mock(side_effect=FileNotFoundError("private path")))

    def test_non_utf8_stderr_on_failure(self):
        runner = Mock(return_value=subprocess.CompletedProcess([], 1, b"", b"error \xa2 private"))
        with self.assertRaisesRegex(BridgeError, "exited with code 1") as exc:
            run_probe(["local-test"], runner=runner)
        self.assertNotIn("private", str(exc.exception))

    def test_non_utf8_stderr_on_success(self):
        runner = Mock(return_value=subprocess.CompletedProcess([], 0, payload().encode("utf-8"), b"\xa2"))
        self.assertEqual(run_probe(["local-test"], runner=runner)["status"], "PROVIDERS_CHECKED")

    def test_non_utf8_stdout_is_rejected(self):
        runner = Mock(return_value=subprocess.CompletedProcess([], 0, b"\xa2", b""))
        with self.assertRaisesRegex(BridgeError, "not valid UTF-8"):
            run_probe(["local-test"], runner=runner)

    def test_utf8_bom(self):
        runner = Mock(return_value=subprocess.CompletedProcess([], 0, payload().encode("utf-8-sig"), b""))
        self.assertEqual(run_probe(["local-test"], runner=runner)["status"], "PROVIDERS_CHECKED")
