# RiegoBot Product Requirements

## Scale model

- 11, 13 and 17 are pilot Romeos only.
- DreamReader must support N Romeos per collector.
- New controllers matching `Dream<N>_1.mdb` are auto-discovered.
- No operational rule may hardcode a fixed list of Romeo IDs.
- Future topology: N Collectors -> central RiegoBot platform.

## Roles and reporting

RiegoBot will support role-based access and delivery scopes such as management, coordinator, supervisor, irrigator/operator and technician. Reports may be filtered by role, site/fundo and assigned Romeos.

Planned scheduled summaries include weekly incidents, programmed versus executed irrigation/consumption, deviations, unresolved cases, SLA compliance and recurring problems.

## Incident lifecycle

A detected operational incident creates a durable incident record. Notification policies are configurable by incident type, severity, site and role.

Lifecycle:

`DETECTED -> NOTIFIED -> WAITING_RESPONSE -> IN_PROGRESS -> PENDING_VALIDATION -> RESOLVED -> CLOSED`

If the assigned irrigator does not respond or resolve the incident within the configured SLA, RiegoBot must resend WhatsApp alerts repeatedly and escalate to supervisor/coordinator according to policy. Acknowledgement alone does not close an incident.

The irrigator can respond through WhatsApp with an observation and photo. Evidence is stored centrally and must be visible from the monitoring center.

Closure can require both:
- human evidence/confirmation;
- system validation that the Dream condition no longer persists.

## Monitoring center

The central monitoring application will show incident status, Romeo, responsible person, timestamps, SLA, number of reminders, escalation level, observation, photo evidence, history and KPIs.

## Safety boundary

Dream access remains read-only. RiegoBot does not actuate valves or alter irrigation programs in the initial architecture.
