from pathlib import Path


def session_output_path(project_root: Path, site_id: str, collector_id: str, session_id: str) -> Path:
    path = project_root / "output" / site_id / collector_id / session_id
    path.mkdir(parents=True, exist_ok=False)
    return path
