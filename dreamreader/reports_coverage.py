from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def summarize_reportsrt_coverage(project_root: Path) -> dict[str, Any]:
    output_root = project_root / "output"
    candidates: list[tuple[float, Path]] = []
    if output_root.exists():
        for path in output_root.rglob("reportsrt_coverage_candidate.json"):
            try:
                candidates.append((path.stat().st_mtime, path))
            except OSError:
                continue

    if not candidates:
        return {"success": False, "error": "No existe analisis de cobertura ReportsRT."}

    path = max(candidates, key=lambda item: item[0])[1]
    raw = _read_json(path)
    rows = [raw] if isinstance(raw, dict) else [row for row in raw if isinstance(row, dict)] if isinstance(raw, list) else []

    total = sum(int(row.get("EventCount") or 0) for row in rows)
    return {
        "success": True,
        "sourceFile": str(path),
        "dreamValuesFound": len(rows),
        "totalEventsReported": total,
        "coverage": rows,
        "interpretationStatus": "CANDIDATE",
        "safeNote": "Esta salida solo indica que valores Dream existen en ReportsRT y su cobertura temporal; no interpreta estado operativo.",
    }
