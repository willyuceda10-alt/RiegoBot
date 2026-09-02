from pathlib import Path


def session_log_path(project_root: Path, site_id: str, collector_id: str, session_id: str) -> Path:
    directory = project_root / "logs" / site_id / collector_id
    directory.mkdir(parents=True, exist_ok=True)
    return directory / f"DreamReader_{session_id}.log"
