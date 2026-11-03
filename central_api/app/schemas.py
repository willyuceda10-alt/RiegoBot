from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


DeliveryMode = Literal["TEST_REPLAY", "PRODUCTION"]


class CentralIncident(BaseModel):
    episodeId: str = Field(min_length=1, max_length=80)
    romeoId: str = Field(min_length=1, max_length=50)
    fundoId: str | None = None
    incidentType: str = Field(min_length=1, max_length=100)
    severity: str = Field(min_length=1, max_length=30)
    firstDetectedAt: datetime
    lastSignalAt: datetime
    signalCount: int = Field(default=1, ge=1)
    programCandidateId: str | None = None
    objectCandidateId: str | None = None
    requiresPhotoEvidence: bool = False
    requiresObservation: bool = True
    requiresResolutionValidation: bool = True
    sourcePayload: dict[str, Any] = Field(default_factory=dict)


class CollectorIncidentBatch(BaseModel):
    batchId: str = Field(min_length=1, max_length=120)
    siteId: str = Field(min_length=1, max_length=80)
    collectorId: str = Field(min_length=1, max_length=120)
    collectedAt: datetime
    deliveryMode: DeliveryMode
    incidents: list[CentralIncident]


class CollectorBatchResult(BaseModel):
    success: bool
    batchId: str
    alreadyProcessed: bool
    incidentCount: int
    insertedIncidents: int
    updatedIncidents: int
    deliveryMode: DeliveryMode
