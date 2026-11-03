CREATE TABLE IF NOT EXISTS sites (
    site_id text PRIMARY KEY,
    name text NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS collectors (
    collector_id text PRIMARY KEY,
    site_id text NOT NULL REFERENCES sites(site_id),
    name text NOT NULL,
    last_seen_at timestamptz,
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS romeos (
    site_id text NOT NULL REFERENCES sites(site_id),
    romeo_id text NOT NULL,
    display_name text NOT NULL,
    fundo_id text,
    last_seen_at timestamptz,
    created_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (site_id, romeo_id)
);

CREATE TABLE IF NOT EXISTS collector_ingest_batches (
    batch_id text PRIMARY KEY,
    site_id text NOT NULL REFERENCES sites(site_id),
    collector_id text NOT NULL REFERENCES collectors(collector_id),
    collected_at timestamptz NOT NULL,
    received_at timestamptz NOT NULL DEFAULT now(),
    delivery_mode text NOT NULL CHECK (delivery_mode IN ('TEST_REPLAY', 'PRODUCTION')),
    incident_count integer NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS app_users (
    user_id text PRIMARY KEY,
    display_name text NOT NULL,
    whatsapp_number text,
    enabled boolean NOT NULL DEFAULT true,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS user_role_assignments (
    assignment_id text PRIMARY KEY,
    user_id text NOT NULL REFERENCES app_users(user_id),
    role_name text NOT NULL CHECK (role_name IN ('REGADOR', 'SUPERVISOR', 'COORDINADOR', 'JEFE', 'ADMIN')),
    site_id text REFERENCES sites(site_id),
    fundo_id text,
    romeo_id text,
    incident_type text,
    shift_start time,
    shift_end time,
    priority integer NOT NULL DEFAULT 0,
    enabled boolean NOT NULL DEFAULT true,
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS incident_evidence_policies (
    incident_type text PRIMARY KEY,
    requires_photo_evidence boolean NOT NULL DEFAULT false,
    requires_observation boolean NOT NULL DEFAULT true,
    requires_resolution_validation boolean NOT NULL DEFAULT true,
    enabled boolean NOT NULL DEFAULT true,
    updated_at timestamptz NOT NULL DEFAULT now()
);

INSERT INTO incident_evidence_policies (
    incident_type,
    requires_photo_evidence,
    requires_observation,
    requires_resolution_validation
)
VALUES ('*', false, true, true)
ON CONFLICT (incident_type) DO NOTHING;

CREATE TABLE IF NOT EXISTS incidents (
    episode_id text PRIMARY KEY,
    site_id text NOT NULL REFERENCES sites(site_id),
    collector_id text NOT NULL REFERENCES collectors(collector_id),
    romeo_id text NOT NULL,
    fundo_id text,
    incident_type text NOT NULL,
    severity text NOT NULL,
    program_candidate_id text,
    object_candidate_id text,
    first_detected_at timestamptz NOT NULL,
    last_signal_at timestamptz NOT NULL,
    signal_count integer NOT NULL DEFAULT 1,
    status text NOT NULL DEFAULT 'DETECTED',
    delivery_mode text NOT NULL CHECK (delivery_mode IN ('TEST_REPLAY', 'PRODUCTION')),
    routing_status text,
    primary_user_id text REFERENCES app_users(user_id),
    supervisor_user_id text REFERENCES app_users(user_id),
    coordinator_user_id text REFERENCES app_users(user_id),
    response_due_at timestamptz,
    supervisor_escalation_at timestamptz,
    coordinator_escalation_at timestamptz,
    requires_photo_evidence boolean NOT NULL DEFAULT false,
    requires_observation boolean NOT NULL DEFAULT true,
    requires_resolution_validation boolean NOT NULL DEFAULT true,
    source_payload jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_incidents_status
    ON incidents(status);
CREATE INDEX IF NOT EXISTS idx_incidents_romeo
    ON incidents(site_id, romeo_id);
CREATE INDEX IF NOT EXISTS idx_incidents_detected
    ON incidents(first_detected_at DESC);
CREATE INDEX IF NOT EXISTS idx_incidents_type
    ON incidents(incident_type);

CREATE TABLE IF NOT EXISTS incident_events (
    event_id bigserial PRIMARY KEY,
    episode_id text NOT NULL REFERENCES incidents(episode_id),
    event_type text NOT NULL,
    from_status text,
    to_status text,
    actor_type text NOT NULL,
    actor_id text,
    occurred_at timestamptz NOT NULL DEFAULT now(),
    observation text,
    metadata jsonb NOT NULL DEFAULT '{}'::jsonb
);

CREATE INDEX IF NOT EXISTS idx_incident_events_episode
    ON incident_events(episode_id, occurred_at);

CREATE TABLE IF NOT EXISTS incident_evidence (
    evidence_id bigserial PRIMARY KEY,
    episode_id text NOT NULL REFERENCES incidents(episode_id),
    evidence_type text NOT NULL,
    storage_ref text NOT NULL,
    file_name text,
    mime_type text,
    actor_id text,
    received_at timestamptz NOT NULL DEFAULT now(),
    metadata jsonb NOT NULL DEFAULT '{}'::jsonb
);

CREATE TABLE IF NOT EXISTS notification_outbox (
    outbox_id text PRIMARY KEY,
    episode_id text NOT NULL REFERENCES incidents(episode_id),
    channel text NOT NULL,
    action text NOT NULL,
    recipient_role text NOT NULL,
    recipient_user_id text REFERENCES app_users(user_id),
    scheduled_at timestamptz NOT NULL,
    delivery_mode text NOT NULL CHECK (delivery_mode IN ('TEST_REPLAY', 'PRODUCTION')),
    status text NOT NULL,
    attempt_count integer NOT NULL DEFAULT 0,
    last_attempt_at timestamptz,
    sent_at timestamptz,
    provider_message_id text,
    payload jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_notification_outbox_due
    ON notification_outbox(status, scheduled_at);

CREATE OR REPLACE VIEW vw_incidents_monitoring AS
SELECT
    i.episode_id,
    i.site_id,
    i.romeo_id,
    i.fundo_id,
    i.incident_type,
    i.severity,
    i.first_detected_at,
    i.last_signal_at,
    i.signal_count,
    i.status,
    i.delivery_mode,
    i.routing_status,
    i.primary_user_id,
    u.display_name AS primary_assignee_name,
    i.response_due_at,
    i.supervisor_escalation_at,
    i.coordinator_escalation_at,
    i.requires_photo_evidence,
    i.requires_observation,
    i.updated_at
FROM incidents i
LEFT JOIN app_users u
    ON u.user_id = i.primary_user_id;

CREATE OR REPLACE VIEW vw_incident_kpis_daily AS
SELECT
    date_trunc('day', first_detected_at) AS incident_day,
    site_id,
    romeo_id,
    incident_type,
    severity,
    delivery_mode,
    COUNT(*) AS incident_count,
    COUNT(*) FILTER (
        WHERE status NOT IN ('RESOLVED', 'CLOSED')
    ) AS active_count,
    COUNT(*) FILTER (
        WHERE status IN ('RESOLVED', 'CLOSED')
    ) AS resolved_count
FROM incidents
GROUP BY
    date_trunc('day', first_detected_at),
    site_id,
    romeo_id,
    incident_type,
    severity,
    delivery_mode;
