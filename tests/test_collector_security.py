"""Local regressions for credential boundaries, durable limits and subprocess cleanup."""
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import io
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from unittest.mock import patch

from dreamreader.collector import (
    MAX_BATCH_BYTES, MAX_RESPONSE_BYTES, Outbox, OutboxFull, cycle, export_rows, ingest_endpoint, send_payload,
)


@contextmanager
def local_server(handler):
    server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}"
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


class QuietHandler(BaseHTTPRequestHandler):
    def log_message(self, *_args):
        pass


class CollectorSecurityTests(unittest.TestCase):
    def test_endpoint_rejects_plaintext_userinfo_and_url_suffix_tricks(self):
        for url in ("http://127.0.0.1:80@attacker.test", "http://127.0.0.1.attacker.test",
                    "http://attacker.test", "https://user:password@project.supabase.co",
                    "https://project.supabase.co/path", "https://project.supabase.co?x=1",
                    "https://project.supabase.co#x", "https://project.supabase.co\\@host",
                    " https://project.supabase.co", "https://project.supabase.co:99999"):
            with self.subTest(url=url), self.assertRaises(ValueError):
                ingest_endpoint(url)
        self.assertEqual(ingest_endpoint("https://project.supabase.co/"),
                         "https://project.supabase.co/functions/v1/ingest")
        self.assertEqual(ingest_endpoint("http://127.0.0.1:55321"),
                         "http://127.0.0.1:55321/functions/v1/ingest")

    def test_redirect_never_receives_collector_token(self):
        sink_requests = []

        class Sink(QuietHandler):
            def do_GET(self):
                sink_requests.append(dict(self.headers))
                self.send_response(200)
                self.end_headers()
                self.wfile.write(b"{}")
            do_POST = do_GET

        with local_server(Sink) as sink:
            class Redirect(QuietHandler):
                def do_POST(self):
                    self.rfile.read(int(self.headers.get("Content-Length", "0")))
                    self.send_response(int(self.path.strip("/")))
                    self.send_header("Location", sink + "/sink")
                    self.send_header("Content-Length", "0")
                    self.end_headers()

            with local_server(Redirect) as origin:
                for code in (301, 302, 303, 307, 308):
                    with self.subTest(code=code), self.assertRaisesRegex(RuntimeError, f"HTTP {code}"):
                        send_payload(origin + f"/{code}", "private-test-token", "{}")
        self.assertEqual(sink_requests, [])

    def test_large_acknowledgement_and_invalid_token_are_rejected(self):
        opener = unittest.mock.Mock()
        opener.open.return_value = io.BytesIO(b" " * (MAX_RESPONSE_BYTES + 1))
        with patch("dreamreader.collector.build_opener", return_value=opener):
            with self.assertRaisesRegex(RuntimeError, "response limit"):
                send_payload("http://127.0.0.1/", "test-token", "{}")
        with self.assertRaisesRegex(ValueError, "single-line") as result:
            send_payload("http://127.0.0.1/", "private-token\nheader", "{}")
        self.assertNotIn("private-token", str(result.exception))

    def test_extractor_drains_stderr_and_does_not_inherit_application_secrets(self):
        script = ("import json,os,sys; sys.stderr.write('x'*262144); sys.stderr.flush(); "
                  "print(json.dumps({'token':os.environ.get('RIEGOBOT_COLLECTOR_TOKEN'),"
                  "'other':os.environ.get('SUPABASE_SERVICE_ROLE_KEY')}))")
        with patch.dict(os.environ, {"RIEGOBOT_COLLECTOR_TOKEN": "test-secret",
                                     "SUPABASE_SERVICE_ROLE_KEY": "second-secret"}):
            result = list(export_rows([sys.executable, "-c", script], timeout=5))
        self.assertEqual(result, [{"token": None, "other": None}])

    def test_extractor_timeout_terminates_child(self):
        started = time.monotonic()
        real_popen = subprocess.Popen
        children = []

        def spawn(*args, **kwargs):
            child = real_popen(*args, **kwargs)
            children.append(child)
            return child

        with patch("dreamreader.collector.subprocess.Popen", side_effect=spawn):
            with self.assertRaises(TimeoutError):
                list(export_rows([sys.executable, "-c", "import time; time.sleep(30)"], timeout=0.2))
        self.assertLess(time.monotonic() - started, 3)
        self.assertIsNotNone(children[0].poll())

    def test_extractor_bad_row_closes_process(self):
        rows = export_rows([sys.executable, "-c", "import time; print('not json', flush=True); time.sleep(30)"], timeout=5)
        started = time.monotonic()
        with self.assertRaises(json.JSONDecodeError):
            list(rows)
        self.assertLess(time.monotonic() - started, 3)

    def test_cycle_enforces_readonly_at_public_entry_point(self):
        with patch("dreamreader.collector.export_rows") as extract:
            with self.assertRaisesRegex(RuntimeError, "readOnly"):
                cycle({"readOnly": False}, None, "2026-09-01")
            extract.assert_not_called()


class OutboxLimitsTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = Path(self.temp.name) / "outbox.sqlite"
        self.boxes = []

    def tearDown(self):
        for box in self.boxes:
            box.db.close()
        self.temp.cleanup()

    def box(self, **kwargs):
        box = Outbox(self.path, **kwargs)
        self.boxes.append(box)
        return box

    def test_capacity_rolls_back_seen_and_preserves_existing_batch(self):
        box = self.box(max_batches=1)
        box.stage([{"source_key": "first"}], "collector")
        with self.assertRaises(OutboxFull):
            box.stage([{"source_key": "second"}], "collector")
        self.assertEqual(box.db.execute("SELECT key FROM seen").fetchall(), [("first",)])
        with patch("dreamreader.collector.send_payload", side_effect=lambda _url, _token, body, **_kwargs: json.loads(body)):
            self.assertEqual(box.flush("http://127.0.0.1", "test-token"), 1)
        self.assertEqual(box.stage([{"source_key": "second"}], "collector"), 1)

    def test_byte_capacity_has_no_partial_dedup_commit(self):
        box = self.box(max_pending_bytes=1)
        with self.assertRaises(OutboxFull):
            box.stage([{"source_key": "one"}], "collector")
        self.assertEqual(box.db.execute("SELECT count(*) FROM seen").fetchone()[0], 0)

    def test_database_page_limit_retains_committed_rows(self):
        box = self.box(max_db_bytes=64 * 1024)
        box.stage([{"source_key": "saved"}], "collector")
        with self.assertRaises(OutboxFull):
            box.stage([{"source_key": "large", "data": "x" * (128 * 1024)}], "collector")
        self.assertEqual(box.db.execute("SELECT key FROM seen").fetchall(), [("saved",)])
        self.assertEqual(box.db.execute("SELECT count(*) FROM outbox").fetchone()[0], 1)

    def test_large_utf8_rows_split_below_ingest_limit_with_full_envelope(self):
        box = self.box()
        rows = [{"source_key": str(number), "data": "🌱" * 60000} for number in range(20)]
        self.assertEqual(box.stage(rows, "riego-ñ🌱"), len(rows))
        recovered = []
        batches = box.db.execute("SELECT id,payload,payload_bytes FROM outbox ORDER BY rowid").fetchall()
        self.assertGreater(len(batches), 1)
        for batch_id, payload, stored_size in batches:
            self.assertLessEqual(len(payload.encode("utf-8")), MAX_BATCH_BYTES)
            self.assertEqual(stored_size, len(payload.encode("utf-8")))
            body = json.loads(payload)
            self.assertEqual(body["batch_id"], batch_id)
            self.assertEqual(body["collector_id"], "riego-ñ🌱")
            recovered.extend(body["rows"])
        self.assertEqual(recovered, rows)

    def test_split_batch_count_capacity_rolls_back_every_new_batch_and_seen_key(self):
        box = self.box(max_batches=2)
        box.stage([{"source_key": "existing"}], "collector")
        rows = [{"source_key": str(number), "data": "🌱" * 60000} for number in range(20)]
        with self.assertRaises(OutboxFull):
            box.stage(rows, "collector")
        self.assertEqual(box.db.execute("SELECT key FROM seen").fetchall(), [("existing",)])
        self.assertEqual(box.db.execute("SELECT count(*) FROM outbox").fetchone()[0], 1)

    def test_split_batch_byte_capacity_rolls_back_every_new_batch_and_seen_key(self):
        box = self.box(max_pending_bytes=MAX_BATCH_BYTES + 1000)
        box.stage([{"source_key": "existing"}], "collector")
        rows = [{"source_key": str(number), "data": "🌱" * 60000} for number in range(20)]
        with self.assertRaises(OutboxFull):
            box.stage(rows, "collector")
        self.assertEqual(box.db.execute("SELECT key FROM seen").fetchall(), [("existing",)])
        self.assertEqual(box.db.execute("SELECT count(*) FROM outbox").fetchone()[0], 1)

    def test_oversized_single_row_is_rejected_without_partial_staging(self):
        box = self.box()
        with self.assertRaisesRegex(ValueError, "One Dream row exceeds"):
            box.stage([{"source_key": "first"}, {"source_key": "huge", "data": "x" * MAX_BATCH_BYTES}], "collector")
        self.assertEqual(box.db.execute("SELECT count(*) FROM seen").fetchone()[0], 0)
        self.assertEqual(box.db.execute("SELECT count(*) FROM outbox").fetchone()[0], 0)

    def test_small_rows_are_also_split_at_api_row_count_limit(self):
        box = self.box()
        rows = [{"source_key": str(number)} for number in range(501)]
        self.assertEqual(box.stage(rows, "collector"), 501)
        counts = [len(json.loads(row[0])["rows"]) for row in box.db.execute("SELECT payload FROM outbox ORDER BY rowid")]
        self.assertEqual(counts, [250, 250, 1])

    def test_flush_is_bounded_and_requires_matching_acknowledgement(self):
        box = self.box()
        for number in range(3):
            box.stage([{"source_key": str(number)}], "collector")
        with patch("dreamreader.collector.send_payload", return_value={"batch_id": "wrong"}):
            with self.assertRaisesRegex(RuntimeError, "mismatch"):
                box.flush("http://127.0.0.1", "test-token")
        self.assertEqual(box.db.execute("SELECT count(*) FROM outbox").fetchone()[0], 3)
        with patch("dreamreader.collector.send_payload", side_effect=lambda _url, _token, body, **_kwargs: json.loads(body)):
            self.assertEqual(box.flush("http://127.0.0.1", "test-token", max_batches=2), 2)
        self.assertEqual(box.db.execute("SELECT count(*) FROM outbox").fetchone()[0], 1)

    def test_schema_upgrade_preserves_existing_payload(self):
        db = sqlite3.connect(self.path)
        with db:
            db.executescript("CREATE TABLE seen(key TEXT PRIMARY KEY); CREATE TABLE outbox(id TEXT PRIMARY KEY,payload TEXT NOT NULL);")
            db.execute("INSERT INTO outbox VALUES('id', ?)", ('{"text":"riego á"}',))
        db.close()
        box = self.box()
        payload, length = box.db.execute("SELECT payload,payload_bytes FROM outbox").fetchone()
        self.assertEqual(length, len(payload.encode("utf-8")))

    def test_mascot_and_scheduled_task_cannot_run_same_cycle(self):
        first, second = self.box(), self.box()
        with first.exclusive_cycle():
            with self.assertRaisesRegex(RuntimeError, "already running"):
                with second.exclusive_cycle():
                    self.fail("A second collector acquired an active cycle lock")
        with second.exclusive_cycle():
            pass


if __name__ == "__main__":
    unittest.main()
