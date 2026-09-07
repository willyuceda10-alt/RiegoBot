-- Keep queue acquisition and incident detail queries bounded as history grows.
create index jobs_ready on public.jobs(available_at,id) where status='pending';
create index jobs_expired_leases on public.jobs(locked_at) where status='processing';
create index jobs_site_outbound on public.jobs((payload->>'site_id'),id desc) where kind='outbound';
create index incidents_site_recent on public.incidents(site_id,id desc);
create index incidents_due_reminder on public.incidents(next_reminder_at) where status<>'resolved';
create index incidents_due_escalation on public.incidents(next_escalation_at) where status<>'resolved';
create index incident_events_case on public.incident_events(incident_id,id);
create index evidence_case on public.evidence(incident_id,created_at);
create index messages_site_recent on public.messages(site_id,id desc);
create index contacts_active_phone on public.contacts(phone) where active;
create index observations_site_entity_recent on public.observations(site_id,entity,source_at desc);
