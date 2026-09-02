from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path
from typing import Any

def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8-sig"))

def summarize_shared_dream_coverage(project_root: Path) -> dict[str, Any]:
    output_root = project_root / "output"
    candidates: list[tuple[float, Path]] = []
    if output_root.exists():
        for path in output_root.rglob("shared_dream_coverage_candidate.json"):
            try:
                candidates.append((path.stat().st_mtime, path))
            except OSError:
                continue
    if not candidates:
        return {"success": False, "error": "No existe analisis de cobertura Dream en bases compartidas."}

    path = max(candidates, key=lambda item: item[0])[1]
    raw = _read_json(path)
    rows = [raw] if isinstance(raw, dict) else [row for row in raw if isinstance(row, dict)] if isinstance(raw, list) else []

    by_dream: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        by_dream[str(row.get("DreamRaw"))].append(row)

    return {
        "success": True,
        "sourceFile": str(path),
        "rowCount": len(rows),
        "dreamValues": sorted(by_dream.keys()),
        "coverageByDream": {
            dream: [
                {
                    "database": row.get("Database"),
                    "table": row.get("TableName"),
                    "rowCount": row.get("RowCount"),
                }
                for row in items
            ]
            for dream, items in sorted(by_dream.items())
        },
        "interpretationStatus": "CANDIDATE",
        "safeNote": "Esta salida localiza donde existen valores Dream en bases compartidas; no interpreta semantica operativa.",
    }
