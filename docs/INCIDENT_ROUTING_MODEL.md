# Incident Routing Model

RiegoBot routes every incident episode through an explicit assignment model. No person, phone number, Fundo or shift is inferred from Dream data.

## Roles

- REGADOR: primary incident assignee and first WhatsApp recipient.
- SUPERVISOR: first escalation recipient.
- COORDINADOR: second escalation recipient.

## User record

Each user can define:

- userId
- displayName
- role
- whatsappNumber
- enabled

## Assignment record

Each assignment can define:

- assignmentId
- userId
- role
- romeoIds
- fundoIds
- incidentTypes
- shift
- priority
- enabled

An empty list or `["*"]` is treated as a wildcard scope. A higher priority wins when multiple assignments match.

## Shift

Optional shift filters use Dream local timestamps and support:

- days: Python weekday numbers, Monday=0 through Sunday=6
- startTime: HH:MM
- endTime: HH:MM

Overnight shifts are supported.

## Safety

If no REGADOR assignment matches, the route is `UNASSIGNED` and WhatsApp delivery is blocked. RiegoBot never invents a recipient or phone number. Supervisor and coordinator mappings may also be missing and are reported explicitly.

This candidate routing layer does not send WhatsApp messages. It only resolves who would receive the initial alert and later escalations.
