from pathlib import Path
import json


def resolve_mapping(project_root: Path, entity: str) -> dict | None:
    path = project_root / "mappings" / f"{entity.lower()}.json"
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else None
