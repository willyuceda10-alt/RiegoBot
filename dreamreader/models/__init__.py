from dataclasses import dataclass


@dataclass(frozen=True)
class NormalizedEntity:
    collector_id: str
    site_id: str
    dream_key: str
    dream_id: str
    timestamp: str | None
    source_database: str
    source_table: str
    mapping_status: str
    confidence: float
