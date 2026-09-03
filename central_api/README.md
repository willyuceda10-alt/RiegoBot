# RiegoBot Central API

Version 2.0.0-alpha starts the central cloud control plane.

The Windows DreamReader collector remains a separate, read-only process. The central API never opens Dream MDB files.

## Current endpoints

- GET /health
- POST /api/v1/collector/incident-batches
- GET /api/v1/incidents
- GET /api/v1/incidents/{episode_id}
- GET /api/v1/kpis/incidents

Collector ingestion uses deterministic batch IDs. Reposting the same batch returns alreadyProcessed=true and does not recreate incidents.

Incident upserts preserve central workflow ownership: collector refreshes source evidence but does not reset incident status.

## Delivery modes

Every collector batch is explicitly one of:

- TEST_REPLAY
- PRODUCTION

Stale pilot data is always TEST_REPLAY. Production notification workers must never deliver TEST_REPLAY outbox items.

## PostgreSQL

Apply central_api/sql/001_core.sql to the RiegoBot PostgreSQL database.

Core model includes:

- sites
- collectors
- romeos
- collector_ingest_batches
- app_users
- user_role_assignments
- incident_evidence_policies
- incidents
- incident_events
- incident_evidence
- notification_outbox

Power BI/Fabric-facing starter views:

- vw_incidents_monitoring
- vw_incident_kpis_daily

Photo evidence is optional by default. incident_evidence_policies is the future Azure-managed authority for per-type requirements.

## Local API development

Create an isolated virtual environment, install central_api/requirements.txt, and define:

RIEGOBOT_DATABASE_URL
RIEGOBOT_ENVIRONMENT=development
RIEGOBOT_ALLOW_TEST_REPLAY=true
RIEGOBOT_VERSION=2.0.0-alpha

Run from the repository root with the central_api folder as the working application context:

uvicorn app.main:app --app-dir central_api --host 127.0.0.1 --port 8080

## Azure target

- Azure Container Apps: API and later notification workers
- Azure Database for PostgreSQL Flexible Server: operational source of truth
- Azure Blob Storage: photo/evidence objects
- Azure Service Bus: durable asynchronous notification work
- Azure Key Vault: secrets
- Azure Container Registry: application images
- Fabric / Power BI: realtime monitoring and KPI consumption

Authentication, private networking, managed identity and production WhatsApp delivery are intentionally not enabled in this first cloud scaffold.
