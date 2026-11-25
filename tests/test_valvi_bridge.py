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
        runner = Mock(return_value=subprocess.CompletedProcess([], 0, payload(), ""))
        self.assertEqual(run_probe(["local-test"], runner=runner)["status"], "PROVIDERS_CHECKED")
        self.assertEqual(runner.call_args.kwargs["timeout"], 30)

    def test_runner_failure(self):
        runner = Mock(return_value=subprocess.CompletedProcess([], 1, "", "private error"))
        with self.assertRaises(BridgeError) as exc:
            run_probe(["local-test"], runner=runner)
        self.assertNotIn("private error", str(exc.exception))

    def test_timeout(self):
        with self.assertRaises(BridgeError):
            run_probe(["local-test"], runner=Mock(side_effect=subprocess.TimeoutExpired("local-test", 30)))

    def test_missing_process(self):
        with self.assertRaises(BridgeError):
            run_probe(["local-test"], runner=Mock(side_effect=FileNotFoundError("private path")))
