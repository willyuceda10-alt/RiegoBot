# Durable Incident State

RiegoBot keeps Dream extraction separate from incident workflow state.

Dream events may be reread many times. They must not recreate the same incident, erase operator progress or duplicate workflow history.

## Local development backend

The development backend uses Python's built-in SQLite engine and stores the database under:

`runtime/incident_state.db`

The runtime folder is already excluded from Git.

SQLite is only the portable development backend. The production migration target is Azure Database for PostgreSQL.

## Current tables

### incidents

Stores the current state of each incident episode:

- episode_id
- Romeo/Fundo scope
- incident type and severity
- first/last Dream signal
- signal count
- current workflow status
- routing result and assigned user IDs
- SLA timestamps
- evidence requirements
- created/updated timestamps

### incident_events

Append-only workflow/audit history.

The first synchronization writes one `INCIDENT_CREATED` event. Re-running synchronization does not duplicate that event.

Future WhatsApp responses, assignment changes, acknowledgements, evidence and resolution transitions will append events here rather than rewriting history.

## Idempotency

`episode_id` is the durable incident key.

Repeated Dream extraction updates source/routing/SLA information while preserving the existing workflow status.

For example, if an operator already moved an incident from `DETECTED` to `IN_PROGRESS`, a later Dream poll must not reset it to `DETECTED`.

## Azure migration

The domain model intentionally maps to the future central architecture:

- SQLite `incidents` -> Azure PostgreSQL `incidents`
- SQLite `incident_events` -> Azure PostgreSQL `incident_events`
- collector sync -> central HTTPS API
- local routing IDs -> centrally managed users/RBAC
- future notification outbox -> Service Bus / worker
- future media metadata -> PostgreSQL + Azure Blob Storage

The Dream PC remains read-only and outbound-only.
