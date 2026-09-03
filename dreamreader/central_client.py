from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

from .central_sync import build_central_batch_preview
from .config import load_config


def _is_local_http(url: str) -> bool:
    parsed = urllib.parse.urlparse(url)
    return (
        parsed.scheme == "http"
        and parsed.hostname in {"127.0.0.1", "localhost", "::1"}
    )


def push_central_batch(project_root: Path) -> dict[str, Any]:
    config = load_config(project_root)
    central = config.get("azureCentral") or {}

    if not bool(central.get("enabled", False)):
        return {
            "success": False,
            "blocked": True,
            "reason": "AZURE_CENTRAL_DISABLED",
            "safeNote": "Enable azureCentral only after the central API is configured.",
        }

    base_url = str(central.get("apiBaseUrl") or "").strip().rstrip("/")
    ingest_path = str(
        central.get("ingestPath") or "/api/v1/collector/incident-batches"
    )
    if not base_url:
        return {
            "success": False,
            "blocked": True,
            "reason": "API_BASE_URL_MISSING",
        }

    allow_http_localhost = bool(central.get("allowHttpLocalhost", False))
    if not base_url.lower().startswith("https://"):
        if not (allow_http_localhost and _is_local_http(base_url)):
            return {
                "success": False,
                "blocked": True,
                "reason": "HTTPS_REQUIRED",
                "apiBaseUrl": base_url,
            }

    key_env = str(
        central.get("apiKeyEnvironmentVariable")
        or "RIEGOBOT_COLLECTOR_API_KEY"
    )
    api_key = os.getenv(key_env)
    if not api_key:
        return {
            "success": False,
            "blocked": True,
            "reason": "COLLECTOR_API_KEY_MISSING",
            "environmentVariable": key_env,
        }

    preview = build_central_batch_preview(project_root)
    if not preview.get("success"):
        return preview

    payload_path = Path(str(preview["outputFile"]))
    payload = json.loads(payload_path.read_text(encoding="utf-8"))
    endpoint = base_url + "/" + ingest_path.lstrip("/")
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")

    retries = int(central.get("maxRetries", 3))
    timeout = float(central.get("timeoutSeconds", 15))
    backoff = float(central.get("retryBackoffSeconds", 2))
    collector_id = str(payload.get("collectorId") or "")

    last_error = None
    for attempt in range(1, retries + 1):
        request = urllib.request.Request(
            endpoint,
            data=body,
            method="POST",
            headers={
                "Content-Type": "application/json",
                "Accept": "application/json",
                "X-RiegoBot-Collector-Id": collector_id,
                "X-RiegoBot-Collector-Key": api_key,
            },
        )
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                response_body = response.read().decode("utf-8")
                result = json.loads(response_body) if response_body else {}
                return {
                    "success": True,
                    "attempt": attempt,
                    "endpoint": endpoint,
                    "batchId": payload.get("batchId"),
                    "deliveryMode": payload.get("deliveryMode"),
                    "incidentCount": len(payload.get("incidents", [])),
                    "response": result,
                }
        except urllib.error.HTTPError as exc:
            response_text = exc.read().decode("utf-8", errors="replace")
            last_error = {
                "type": "HTTPError",
                "status": exc.code,
                "body": response_text,
            }
            if 400 <= exc.code < 500 and exc.code != 429:
                break
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            last_error = {
                "type": type(exc).__name__,
                "message": str(exc),
            }

        if attempt < retries:
            time.sleep(backoff * attempt)

    return {
        "success": False,
        "endpoint": endpoint,
        "batchId": payload.get("batchId"),
        "deliveryMode": payload.get("deliveryMode"),
        "attempts": retries,
        "error": last_error,
    }
