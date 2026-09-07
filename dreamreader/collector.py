"""Bounded durable outbox; the PowerShell bridge opens MDB files read-only."""
from __future__ import annotations

import argparse
from collections import deque
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
import hashlib
import json
import logging
import os
from pathlib import Path
import queue
import sqlite3
import subprocess
import threading
import time
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener
import uuid
from zoneinfo import ZoneInfo

from . import PROJECT_ROOT
from .config import load_config

MAX_RESPONSE_BYTES = 64 * 1024
MAX_ROW_BYTES = 1024 * 1024
# The ingestion API accepts 4 MiB; leave headroom and include the UTF-8 envelope.
MAX_BATCH_BYTES = 3 * 1024 * 1024
MAX_BATCH_ROWS = 250


def ingest_endpoint(base_url: str) -> str:
    """Accept an origin, never credentials, suffix tricks or plaintext remote URLs."""
    if not isinstance(base_url, str) or any(c.isspace() or ord(c) < 32 for c in base_url) or "\\" in base_url:
        raise ValueError("Supabase URL must be an HTTPS origin")
    parts = urlsplit(base_url)
    try:
        port = parts.port
    except ValueError:
        raise ValueError("Supabase URL has an invalid port") from None
    if (not parts.hostname or parts.username is not None or parts.password is not None
            or parts.path not in ("", "/") or parts.query or parts.fragment
            or port == 0):
        raise ValueError("Supabase URL must contain only an origin, without credentials or a path")
    if parts.scheme != "https" and not (parts.scheme == "http" and parts.hostname in ("127.0.0.1", "::1")):
        raise ValueError("HTTPS is required except for a loopback development server")
    return base_url.rstrip("/") + "/functions/v1/ingest"


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        # The collector credential must never follow a redirect to another server.
        return None


def send_payload(url: str, token: str, payload: str, timeout: float = 30) -> dict:
    if not token or any(ord(c) < 33 or ord(c) > 126 for c in token):
        raise ValueError("Collector token must be a nonempty single-line ASCII credential")
    request = Request(url, data=payload.encode("utf-8"),
                      headers={"Content-Type": "application/json"}, method="POST")
    request.add_unredirected_header("x-collector-token", token)
    deadline = time.monotonic() + timeout
    try:
        with build_opener(_NoRedirect()).open(request, timeout=timeout) as response:
            raw = bytearray()
            while True:
                if time.monotonic() >= deadline:
                    raise TimeoutError("Collector acknowledgement exceeded its time limit")
                chunk = response.read1(min(4096, MAX_RESPONSE_BYTES + 1 - len(raw)))
                if not chunk:
                    break
                raw.extend(chunk)
                if len(raw) > MAX_RESPONSE_BYTES:
                    raise RuntimeError("Collector acknowledgement exceeds the response limit")
            result = json.loads(raw)
            if not isinstance(result, dict):
                raise RuntimeError("Invalid collector acknowledgement")
            return result
    except HTTPError as exc:
        # Do not reflect response bodies, URLs or environment credentials into logs.
        exc.close()
        raise RuntimeError(f"Collector endpoint returned HTTP {exc.code}; batch retained") from None
    except (URLError, OSError):
        raise RuntimeError("Collector endpoint unavailable; batch retained") from None


class OutboxFull(RuntimeError):
    pass


def _batch_payloads(rows: list[dict], collector_id: str):
    def new_batch():
        batch_id = str(uuid.uuid4())
        envelope = json.dumps({"batch_id": batch_id, "collector_id": collector_id, "rows": []},
                              ensure_ascii=False, separators=(",", ":"))
        header = envelope[:-2]
        return batch_id, header, len(envelope.encode("utf-8"))

    batch, header, size = new_batch()
    serialized = []
    for row in rows:
        encoded = json.dumps(row, ensure_ascii=False, separators=(",", ":"))
        row_bytes = len(encoded.encode("utf-8"))
        if len(header.encode("utf-8")) + row_bytes + 2 > MAX_BATCH_BYTES:
            raise ValueError("One Dream row exceeds the 3 MiB batch limit including its envelope; this staging operation was rolled back")
        if serialized and (len(serialized) >= MAX_BATCH_ROWS or size + row_bytes + 1 > MAX_BATCH_BYTES):
            yield batch, header + ",".join(serialized) + "]}", size
            batch, header, size = new_batch()
            serialized = []
        size += row_bytes + (1 if serialized else 0)
        serialized.append(encoded)
    if serialized:
        yield batch, header + ",".join(serialized) + "]}", size


class Outbox:
    def __init__(self, path: Path, *, max_batches: int = 2000,
                 max_pending_bytes: int = 128 * 1024 * 1024,
                 max_db_bytes: int = 512 * 1024 * 1024):
        self.path = Path(path).resolve()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.max_batches = max(1, int(max_batches))
        self.max_pending_bytes = max(1, int(max_pending_bytes))
        self.db = sqlite3.connect(self.path, timeout=5)
        self.db.execute("PRAGMA journal_mode=WAL")
        self.db.execute("PRAGMA busy_timeout=5000")
        page_size = self.db.execute("PRAGMA page_size").fetchone()[0]
        self.db.execute(f"PRAGMA max_page_count={max(1, int(max_db_bytes) // page_size)}")
        self.db.executescript("CREATE TABLE IF NOT EXISTS seen(key TEXT PRIMARY KEY); "
                             "CREATE TABLE IF NOT EXISTS outbox(id TEXT PRIMARY KEY,payload TEXT NOT NULL);")
        with self.db:
            self.db.execute("BEGIN IMMEDIATE")
            if "payload_bytes" not in {r[1] for r in self.db.execute("PRAGMA table_info(outbox)")}:
                self.db.execute("ALTER TABLE outbox ADD COLUMN payload_bytes INTEGER NOT NULL DEFAULT 0")
                self.db.execute("UPDATE outbox SET payload_bytes=length(CAST(payload AS BLOB))")

    @contextmanager
    def exclusive_cycle(self):
        """OS lock shared by the mascot and scheduled collector; released on crash."""
        with self.path.with_suffix(".lock").open("a+b") as lock:
            lock.seek(0, os.SEEK_END)
            if lock.tell() == 0:
                lock.write(b"0")
                lock.flush()
            lock.seek(0)
            try:
                if os.name == "nt":
                    import msvcrt
                    msvcrt.locking(lock.fileno(), msvcrt.LK_NBLCK, 1)
                else:
                    import fcntl
                    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except OSError:
                raise RuntimeError("Another collector cycle is already running") from None
            try:
                yield
            finally:
                lock.seek(0)
                if os.name == "nt":
                    msvcrt.locking(lock.fileno(), msvcrt.LK_UNLCK, 1)
                else:
                    fcntl.flock(lock, fcntl.LOCK_UN)

    def stage(self, rows: list[dict], collector_id: str):
        try:
            with self.db:
                # Capacity and deduplication belong to the same write transaction.
                self.db.execute("BEGIN IMMEDIATE")
                fresh = []
                for row in rows:
                    if self.db.execute("INSERT OR IGNORE INTO seen VALUES(?)",
                                       (row.get("revision_key", row["source_key"]),)).rowcount:
                        fresh.append(row)
                if fresh:
                    count, pending = self.db.execute("SELECT count(*),coalesce(sum(payload_bytes),0) FROM outbox").fetchone()
                    for batch, payload, size in _batch_payloads(fresh, collector_id):
                        if count >= self.max_batches or pending + size > self.max_pending_bytes:
                            raise OutboxFull("Local queue limit reached; pending batches retained. Restore connectivity before reading more Dream data.")
                        self.db.execute("INSERT INTO outbox(id,payload,payload_bytes) VALUES(?,?,?)",
                                        (batch, payload, size))
                        count += 1
                        pending += size
            return len(fresh)
        except sqlite3.OperationalError as exc:
            if getattr(exc, "sqlite_errorcode", None) == sqlite3.SQLITE_FULL:
                raise OutboxFull("Local database disk limit reached; data retained in Dream and the pending queue") from None
            raise

    def flush(self, url: str, token: str, *, max_batches: int = 20, max_seconds: float = 60):
        sent = 0
        deadline = time.monotonic() + max_seconds
        # Read one payload at a time: a long outage must not load the whole queue in RAM.
        while sent < max_batches and time.monotonic() < deadline:
            item = self.db.execute("SELECT id,payload FROM outbox ORDER BY rowid LIMIT 1").fetchone()
            if item is None:
                break
            bid, payload = item
            result = send_payload(url, token, payload, timeout=max(0.1, min(30, deadline - time.monotonic())))
            if result.get("batch_id") != bid:
                raise RuntimeError("Batch acknowledgement mismatch")
            with self.db:
                self.db.execute("DELETE FROM outbox WHERE id=?", (bid,))
            sent += 1
        return sent


def normalized(row: dict, zone: str) -> dict:
    timestamp = datetime.fromisoformat(row["source_at"])
    if timestamp.tzinfo is None:
        timestamp = timestamp.replace(tzinfo=ZoneInfo(zone))
    row["source_at"] = timestamp.astimezone(timezone.utc).isoformat()
    canonical = json.dumps(row, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    row["revision_key"] = hashlib.sha256(canonical.encode()).hexdigest()
    mutable = {"LastWM", "LastFert", "LastAccum", "DailyWM", "DailyFert", "DailyAccum", "Programs", "Water_Meters"}
    if row["entity"] in mutable:
        fields = ["System", "Dream", "Unit", "ObjType", "ObjSubType", "ObjNum", "Line", "Tact_Number", "Tact_Index", "ProgName", "WM_GType", "WM_Number"]
        identity = {k: row["data"].get(k) for k in fields}
        identity.update(entity=row["entity"], dream=row["dream_id"])
        if row["entity"].startswith("Daily"):
            identity["date"] = row["source_at"][:10]
        row["source_key"] = hashlib.sha256(json.dumps(identity, sort_keys=True).encode()).hexdigest()
    else:
        row["source_key"] = row["revision_key"]
    return row


def export_rows(command: list[str], timeout: float = 900):
    """Drain both pipes concurrently with bounded buffers and an overall deadline."""
    timeout = min(3600, max(0.1, timeout))
    lines = queue.Queue(maxsize=32)
    errors = deque(maxlen=8)
    done = threading.Event()
    stopped = threading.Event()
    # ACE does not need any application credentials, nor the caller's other secrets.
    allowed = {"systemroot", "windir", "path", "pathext", "temp", "tmp", "userprofile",
               "appdata", "localappdata", "programdata", "programfiles", "programfiles(x86)",
               "commonprogramfiles", "commonprogramfiles(x86)", "systemdrive"}
    environment = {key: value for key, value in os.environ.items() if key.lower() in allowed}
    proc = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                            env=environment, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))

    def stdout_reader():
        try:
            while not stopped.is_set():
                line = proc.stdout.readline(MAX_ROW_BYTES + 1)
                if not line:
                    break
                item = ValueError("Dream export row exceeds the size limit") if len(line) > MAX_ROW_BYTES else line
                while not stopped.is_set():
                    try:
                        lines.put(item, timeout=0.1)
                        break
                    except queue.Full:
                        pass
                if isinstance(item, Exception):
                    break
        finally:
            done.set()

    def stderr_reader():
        while not stopped.is_set():
            chunk = proc.stderr.read(1024)
            if not chunk:
                break
            errors.append(chunk)

    readers = [threading.Thread(target=stdout_reader, daemon=True),
               threading.Thread(target=stderr_reader, daemon=True)]
    for reader in readers:
        reader.start()
    deadline = time.monotonic() + timeout
    try:
        while not done.is_set() or not lines.empty():
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise TimeoutError("Dream extraction exceeded its time limit; pending batches retained")
            try:
                item = lines.get(timeout=min(0.1, remaining))
            except queue.Empty:
                continue
            if isinstance(item, Exception):
                raise item
            if item.strip():
                yield json.loads(item.decode("utf-8-sig"))
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise TimeoutError("Dream extraction exceeded its time limit")
        try:
            returncode = proc.wait(timeout=remaining)
        except subprocess.TimeoutExpired:
            raise TimeoutError("Dream extraction exceeded its time limit") from None
        if returncode:
            # Stderr is bounded and the child never receives the collector token.
            readers[1].join(timeout=2)
            detail = b"".join(errors).decode("utf-8", errors="replace")[-2000:]
            raise RuntimeError("MDB extraction failed: " + detail)
    finally:
        stopped.set()
        if proc.poll() is None:
            proc.kill()
        proc.wait(timeout=5)
        for reader in readers:
            reader.join(timeout=2)
        proc.stdout.close()
        proc.stderr.close()


def cycle(cfg: dict, outbox: Outbox, since: str):
    if not cfg.get("readOnly", False):
        raise RuntimeError("readOnly must be true")
    with outbox.exclusive_cycle():
        root = Path(cfg["discovery"]["rootPath"])
        if not root.is_absolute():
            root = (PROJECT_ROOT / root).resolve()
        enabled = {str(d["dreamId"]) for d in cfg["dreams"] if d.get("enabled", True)}
        settings = cfg["supabase"]
        token = os.environ.get("RIEGOBOT_COLLECTOR_TOKEN")
        if not token:
            raise RuntimeError("Set RIEGOBOT_COLLECTOR_TOKEN in this PC environment")
        endpoint = ingest_endpoint(settings["url"])
        try:
            outbox.flush(endpoint, token)
        except Exception:
            logging.warning("Pending batches retained; retry after extraction")
        powershell = Path(os.environ.get("SystemRoot", "C:/Windows")) / "System32/WindowsPowerShell/v1.0/powershell.exe"
        command = [str(powershell), "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-File",
                   str(PROJECT_ROOT / "scripts/EXPORT_TELEMETRY.ps1"), "-DatabaseRoot", str(root), "-Since", since]
        chunk = []
        chunk_bytes = 0
        rows = export_rows(command, timeout=max(1, float(settings.get("extractionTimeoutSeconds", 900))))
        try:
            for raw in rows:
                if str(raw["dream_id"]) not in enabled:
                    continue
                row = normalized(raw, settings.get("timezone", "America/Bogota"))
                size = len(json.dumps(row, ensure_ascii=False).encode("utf-8"))
                if chunk and chunk_bytes + size > MAX_ROW_BYTES:
                    outbox.stage(chunk, settings["collectorId"])
                    chunk = []
                    chunk_bytes = 0
                chunk.append(row)
                chunk_bytes += size
                if len(chunk) >= 250:
                    outbox.stage(chunk, settings["collectorId"])
                    chunk = []
                    chunk_bytes = 0
            if chunk:
                outbox.stage(chunk, settings["collectorId"])
        finally:
            rows.close()
        outbox.flush(endpoint, token)
        heartbeat = str(uuid.uuid4())
        result = send_payload(endpoint, token, json.dumps({"batch_id": heartbeat,
                              "collector_id": settings["collectorId"], "rows": []}))
        if result.get("batch_id") != heartbeat:
            raise RuntimeError("Heartbeat acknowledgement mismatch")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--once", action="store_true")
    parser.add_argument("--since", help="Initial/history scan start YYYY-MM-DD")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    cfg = load_config(PROJECT_ROOT)
    if not cfg.get("readOnly", False):
        raise RuntimeError("readOnly must be true")
    settings = cfg.get("supabase", {})
    outbox = Outbox(PROJECT_ROOT / "runtime/outbox.sqlite",
                    max_batches=settings.get("maxPendingBatches", 2000),
                    max_pending_bytes=settings.get("maxPendingBytes", 128 * 1024 * 1024),
                    max_db_bytes=settings.get("maxDatabaseBytes", 512 * 1024 * 1024))
    try:
        while True:
            since = args.since or (datetime.now() - timedelta(days=settings.get("lookbackDays", 2))).strftime("%Y-%m-%d")
            try:
                cycle(cfg, outbox, since)
                logging.info("Cycle completed")
            except Exception:
                logging.exception("Collector cycle failed; pending batches retained")
                if args.once:
                    raise
            if args.once:
                break
            time.sleep(max(30, settings.get("intervalSeconds", 60)))
    finally:
        outbox.db.close()


if __name__ == "__main__":
    main()
