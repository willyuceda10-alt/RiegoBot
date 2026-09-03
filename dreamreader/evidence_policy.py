from __future__ import annotations

from pathlib import Path
from typing import Any

from .config import load_config

DEFAULT_EVIDENCE_POLICY: dict[str, bool] = {
    "requiresPhotoEvidence": False,
    "requiresObservation": True,
    "requiresResolutionValidation": True,
}


def resolve_evidence_policy(project_root: Path, incident_type: str) -> dict[str, Any]:
    config = load_config(project_root)
    root = config.get("incidentEvidencePolicies") or {}
    default_policy = {
        **DEFAULT_EVIDENCE_POLICY,
        **(root.get("default") or {}),
    }
    override = (root.get("byIncidentType") or {}).get(str(incident_type), {})
    resolved = {
        **default_policy,
        **override,
    }
    return {
        "incidentType": str(incident_type),
        "requiresPhotoEvidence": bool(resolved.get("requiresPhotoEvidence", False)),
        "requiresObservation": bool(resolved.get("requiresObservation", True)),
        "requiresResolutionValidation": bool(
            resolved.get("requiresResolutionValidation", True)
        ),
        "policySource": str(root.get("policySource") or "LOCAL_CONFIG_UNTIL_AZURE"),
        "mappingStatus": "CANDIDATE",
    }


def evidence_policy_summary(project_root: Path) -> dict[str, Any]:
    config = load_config(project_root)
    root = config.get("incidentEvidencePolicies") or {}
    default_policy = {
        **DEFAULT_EVIDENCE_POLICY,
        **(root.get("default") or {}),
    }
    return {
        "success": True,
        "policySource": str(root.get("policySource") or "LOCAL_CONFIG_UNTIL_AZURE"),
        "default": default_policy,
        "byIncidentType": root.get("byIncidentType") or {},
        "futureAuthority": "AZURE_CENTRAL_POLICY",
        "photoEvidenceDefaultRequired": bool(
            default_policy.get("requiresPhotoEvidence", False)
        ),
    }
