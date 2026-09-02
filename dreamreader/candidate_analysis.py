from __future__ import annotations

import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def find_latest_candidate_events(project_root: Path) -> tuple[Path, list[dict[str, Any]]] | None:
    output_root = project_root / "output"
    if not output_root.exists():
        return None

    candidates: list[tuple[float, Path]] = []
    for path in output_root.rglob("operational_events_candidate.json"):
        try:
            candidates.append((path.stat().st_mtime, path))
        except OSError:
            continue

    if not candidates:
        return None

    path = max(candidates, key=lambda item: item[0])[1]
    try:
        raw = _read_json(path)
    except (OSError, json.JSONDecodeError):
        return None

    if isinstance(raw, dict):
        rows = [raw]
    elif isinstance(raw, list):
        rows = [row for row in raw if isinstance(row, dict)]
    else:
        rows = []

    return path, rows


def summarize_candidate_events(project_root: Path) -> dict[str, Any]:
    found = find_latest_candidate_events(project_root)
    if found is None:
        return {
            "success": False,
            "error": "No existe una extraccion candidata de eventos operativos.",
        }

    path, rows = found
    by_romeo: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        by_romeo[str(row.get("RomeoId") or "UNRESOLVED")].append(row)

    romeo_summaries: list[dict[str, Any]] = []
    global_texts = Counter()
    global_codes = Counter()
    fail_values = Counter()

    for romeo_id, items in sorted(by_romeo.items()):
        texts = Counter(str(row.get("ReportTextRaw") or "").strip() or "<VACIO>" for row in items)
        codes = Counter(str(row.get("ReportCodeRaw")) for row in items)
        fails = Counter(str(row.get("ReportFailRaw")) for row in items)
        states = Counter(str(row.get("StateRaw")) for row in items)

        for key, value in texts.items():
            global_texts[key] += value
        for key, value in codes.items():
            global_codes[key] += value
        for key, value in fails.items():
            fail_values[key] += value

        samples = []
        for row in items[:15]:
            samples.append({
                "timestamp": row.get("Timestamp"),
                "reportCodeRaw": row.get("ReportCodeRaw"),
                "reportTextRaw": row.get("ReportTextRaw"),
                "reportFailRaw": row.get("ReportFailRaw"),
                "stateRaw": row.get("StateRaw"),
                "reportId1Raw": row.get("ReportId1Raw"),
                "reportId2Raw": row.get("ReportId2Raw"),
                "reportId2NameRaw": row.get("ReportId2NameRaw"),
            })

        romeo_summaries.append({
            "romeoId": romeo_id,
            "eventCount": len(items),
            "topReportTexts": [{"text": k, "count": v} for k, v in texts.most_common(15)],
            "topReportCodes": [{"code": k, "count": v} for k, v in codes.most_common(15)],
            "reportFailValues": dict(fails),
            "stateValues": dict(states),
            "recentSamples": samples,
        })

    return {
        "success": True,
        "sourceFile": str(path),
        "totalEvents": len(rows),
        "romeoCount": len(by_romeo),
        "globalTopReportTexts": [{"text": k, "count": v} for k, v in global_texts.most_common(25)],
        "globalTopReportCodes": [{"code": k, "count": v} for k, v in global_codes.most_common(25)],
        "globalReportFailValues": dict(fail_values),
        "romeos": romeo_summaries,
        "interpretationStatus": "CANDIDATE",
        "safeNote": "Los codigos, RepFail, State e IDs se muestran como valores crudos. Todavia no se interpretan como alarmas o valvulas activas.",
    }
