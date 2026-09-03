from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

def _parse(value: Any) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value))
    except ValueError:
        return None

def summarize_freshness_sources(project_root: Path) -> dict[str, Any]:
    candidates=sorted(
        [p for p in (project_root/"output").rglob("freshness_sources_candidate.json")],
        key=lambda p:p.stat().st_mtime,
        reverse=True,
    )
    if not candidates:
        return {"success":False,"error":"No existe freshness_sources_candidate.json."}

    source=candidates[0]
    raw=json.loads(source.read_text(encoding="utf-8-sig"))
    rows=[raw] if isinstance(raw,dict) else raw if isinstance(raw,list) else []
    rows=[r for r in rows if isinstance(r,dict)]
    rows.sort(key=lambda r:_parse(r.get("LatestTimestamp")) or datetime.min, reverse=True)

    by_romeo={}
    for row in rows:
        rid=str(row.get("RomeoId") or "")
        if rid:
            by_romeo.setdefault(rid,[]).append(row)

    return {
        "success":True,
        "sourceFile":str(source),
        "candidateCount":len(rows),
        "romeos":{
            rid:{
                "freshestCandidates":items[:15],
                "freshestTimestamp":items[0].get("LatestTimestamp") if items else None,
            }
            for rid,items in sorted(by_romeo.items(), key=lambda x:x[0])
        },
        "globalFreshestCandidates":rows[:25],
        "interpretationStatus":"CANDIDATE",
        "safeNote":"Este diagnostico solo identifica tablas con timestamps recientes. No interpreta por si mismo estado de riego ni alarmas.",
    }
