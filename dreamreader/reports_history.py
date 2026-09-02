from __future__ import annotations

import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8-sig"))

def summarize_reports_history(project_root: Path) -> dict[str, Any]:
    output_root = project_root / "output"
    candidates: list[tuple[float, Path]] = []
    if output_root.exists():
        for path in output_root.rglob("reports_history_candidate.json"):
            try:
                candidates.append((path.stat().st_mtime, path))
            except OSError:
                continue
    if not candidates:
        return {"success": False, "error": "No existe investigacion candidata de Reports."}

    path = max(candidates, key=lambda item: item[0])[1]
    raw = _read_json(path)
    rows = [raw] if isinstance(raw, dict) else [row for row in raw if isinstance(row, dict)] if isinstance(raw, list) else []

    by_romeo: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        by_romeo[str(row.get("RomeoId") or "UNRESOLVED")].append(row)

    romeos=[]
    for romeo_id, items in sorted(by_romeo.items()):
        texts=Counter(str(row.get("ReportTextRaw") or "").strip() or "<VACIO>" for row in items)
        codes=Counter(str(row.get("ReportCodeRaw")) for row in items)
        transitions=[row for row in items if str(row.get("ReportCodeRaw")) in {"29","30"}]
        failures=[row for row in items if str(row.get("ReportFailRaw")).lower() in {"true","1"}]
        romeos.append({
            "romeoId": romeo_id,
            "eventCount": len(items),
            "latestTimestamp": max((str(row.get("Timestamp") or "") for row in items), default=None),
            "topReportTexts": [{"text":k,"count":v} for k,v in texts.most_common(15)],
            "topReportCodes": [{"code":k,"count":v} for k,v in codes.most_common(15)],
            "valveTransitionCount": len(transitions),
            "failureEventCount": len(failures),
            "recentValveTransitions": transitions[:20],
            "recentFailureEvents": failures[:20],
        })

    return {
        "success": True,
        "sourceFile": str(path),
        "totalEvents": len(rows),
        "romeoCount": len(romeos),
        "romeos": romeos,
        "interpretationStatus": "CANDIDATE",
        "safeNote": "Reports es una fuente historica candidata. Los codigos 29/30 y RepFail se comparan con ReportsRT pero aun no se asumen equivalentes en tiempo real.",
    }
