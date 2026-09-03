# Incident Lifecycle, Evidence and Notification Outbox

This layer is the final local domain block before the Azure central API.

## State machine

Allowed status transitions are explicit and validated. An incident cannot jump arbitrarily between statuses.

Key rule:

- A WhatsApp acknowledgement such as "Ya estoy revisando" moves the incident to `IN_PROGRESS`.
- It does not resolve or close the incident.
- Reminders continue while the incident is `IN_PROGRESS`.
- Only `RESOLVED` or `CLOSED` stop the reminder cycle.

## Resolution evidence

Moving an incident into validation/resolution requires the configured evidence policy.

Current candidate policy:

- observation required
- photo evidence required
- validation required before `RESOLVED`

Photo bytes are not stored in the operational database. The `incident_evidence` table stores metadata and a secure storage reference. In Azure this will point to Azure Blob Storage.

## Notification outbox

The outbox is the durable boundary between domain logic and WhatsApp delivery.

Each item has a deterministic ID based on:

- episode
- action
- recipient role
- scheduled time

This makes repeated scheduler runs idempotent.

Statuses include:

- `PENDING`
- `BLOCKED_UNASSIGNED`
- future: `SENDING`, `SENT`, `FAILED`, `CANCELLED`

If no explicit assignee exists for a required role, the item is stored as `BLOCKED_UNASSIGNED`. Nothing is sent to an invented recipient.

## Azure mapping

Local development:

- SQLite `incidents`
- SQLite `incident_events`
- SQLite `incident_evidence`
- SQLite `notification_outbox`

Central production:

- Azure Database for PostgreSQL
- Azure Blob Storage for photos/evidence
- Azure Service Bus or equivalent worker queue for notification delivery
- HTTPS API for collectors and WhatsApp webhooks
- Fabric/Power BI over the central data model

The Dream machine remains read-only and outbound-only.
