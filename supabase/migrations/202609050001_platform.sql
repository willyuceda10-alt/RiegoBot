-- RiegoBot: all operational writes are authenticated server RPCs.

create extension if not exists pgcrypto;

create table public.sites(id uuid primary key default gen_random_uuid(), name text not null, timezone text not null default 'America/Bogota');

create table public.memberships(user_id uuid references auth.users(id) on delete cascade, site_id uuid references public.sites(id), role text not null check(role in ('admin','supervisor','operator')), primary key(user_id,site_id));

create table public.contacts(id uuid primary key default gen_random_uuid(), site_id uuid not null references public.sites(id), name text not null, phone text not null check(phone ~ '^[0-9]{8,15}$'), role text not null default 'regador', active boolean not null default true, unique(site_id,phone));

create table public.collectors(id uuid primary key default gen_random_uuid(), site_id uuid not null references public.sites(id), name text not null, token_hash text not null, enabled boolean not null default true, last_seen timestamptz, last_error text);

create table public.dreams(site_id uuid references public.sites(id), dream_id text not null check(dream_id ~ '^[0-9]+$'), name text not null, enabled boolean not null default true, primary key(site_id,dream_id));

create table public.batches(id uuid primary key, collector_id uuid references public.collectors(id), received_at timestamptz not null default now());

create table public.observations(id bigint generated always as identity primary key, site_id uuid not null references public.sites(id), dream_id text not null, entity text not null, source_key text not null, source_at timestamptz not null, received_at timestamptz not null default now(), data jsonb not null, unique(site_id,entity,source_key));

create index observations_lookup on public.observations(site_id,dream_id,entity,source_at desc);

create table public.rules(id uuid primary key default gen_random_uuid(),site_id uuid not null references public.sites(id),name text not null,enabled boolean not null default false,

 kind text not null check(kind in ('event','threshold','support')),entity text not null,field text not null default 'RepCode',operator text not null default 'eq' check(operator in ('eq','gt','lt')),value numeric not null,

 dream_id text, severity text not null default 'media' check(severity in ('baja','media','alta','critica')),

 stale_minutes integer not null default 15 check(stale_minutes between 1 and 10080),

 photo_required boolean not null default true, approval_required boolean not null default true,

 reminder_minutes integer not null default 15 check(reminder_minutes between 1 and 10080),

 ack_minutes integer not null default 10 check(ack_minutes between 1 and 10080),

 resolve_minutes integer not null default 60 check(resolve_minutes between 1 and 43200),

 levels jsonb not null default '[]' check(jsonb_typeof(levels)='array'),created_at timestamptz not null default now());

create table public.incidents(id bigint generated always as identity primary key,site_id uuid not null references public.sites(id),rule_id uuid references public.rules(id),

 dream_id text,title text not null,severity text not null default 'media',status text not null default 'open' check(status in ('open','acknowledged','in_progress','pending_review','resolved')),

 asset_key text not null default '',assignee_id uuid references public.contacts(id),level integer not null default 0,

 policy jsonb not null,source_data jsonb not null default '{}',source_active boolean not null default true,

 created_at timestamptz not null default now(),updated_at timestamptz not null default now(),ack_at timestamptz,submitted_at timestamptz,resolved_at timestamptz,

 next_reminder_at timestamptz not null, next_escalation_at timestamptz not null, resolution text);

create unique index incident_episode on public.incidents(site_id,rule_id,asset_key) where status <> 'resolved' and rule_id is not null;

create table public.incident_events(id bigint generated always as identity primary key,incident_id bigint not null references public.incidents(id),actor text not null,action text not null,body text not null default '',created_at timestamptz not null default now());

create table public.evidence(id uuid primary key default gen_random_uuid(),incident_id bigint not null references public.incidents(id),path text not null unique,mime text not null,caption text not null default '',actor text not null,created_at timestamptz not null default now());

create table public.jobs(id bigint generated always as identity primary key,kind text not null check(kind in ('inbound','outbound')),dedupe_key text not null unique,payload jsonb not null,status text not null default 'pending' check(status in ('pending','processing','done','failed','uncertain')),attempts integer not null default 0,available_at timestamptz not null default now(),locked_at timestamptz,lease_id uuid,last_error text,created_at timestamptz not null default now());

create table public.messages(id bigint generated always as identity primary key,external_id text unique,site_id uuid references public.sites(id),phone text not null,direction text not null,body text not null,incident_id bigint references public.incidents(id),delivery_status text,created_at timestamptz not null default now());

create table public.conversations(phone text primary key,site_id uuid references public.sites(id),incident_id bigint references public.incidents(id),mode text not null default 'bot' check(mode in ('bot','human')),last_inbound_at timestamptz);

create table public.audit_log(id bigint generated always as identity primary key,site_id uuid references public.sites(id),actor text not null,action text not null,details jsonb not null default '{}',created_at timestamptz not null default now());



create function public.has_site(s uuid) returns boolean language sql stable security definer set search_path=public as $$

 select exists(select 1 from memberships where site_id=s and user_id=auth.uid())

$$;

revoke all on function public.has_site(uuid) from public;

grant execute on function public.has_site(uuid) to authenticated;

do $$ declare t text; begin

 foreach t in array array['sites','contacts','collectors','dreams','rules','observations','incidents','messages','audit_log'] loop

 execute format('alter table public.%I enable row level security',t);

 execute format('create policy site_read on public.%I for select to authenticated using(public.has_site(%I))',t,case when t='sites' then 'id' else 'site_id' end);

 end loop;

 foreach t in array array['memberships','batches','incident_events','evidence','jobs','conversations'] loop execute format('alter table public.%I enable row level security',t); end loop;

end $$;

create policy own_membership on memberships for select to authenticated using(user_id=auth.uid());

create policy event_read on incident_events for select to authenticated using(exists(select 1 from incidents i where i.id=incident_id and has_site(i.site_id)));

create policy evidence_read on evidence for select to authenticated using(exists(select 1 from incidents i where i.id=incident_id and has_site(i.site_id)));

-- Do not expose collector credentials, even hashed, through the Data API.

revoke all on collectors from anon, authenticated;

grant select(id,site_id,name,enabled,last_seen,last_error) on collectors to authenticated;

grant select on sites,memberships,contacts,dreams,rules,observations,incidents,incident_events,evidence,messages,audit_log to authenticated;

revoke insert,update,delete on all tables in schema public from anon,authenticated;



create function public.enqueue(k text,d text,p jsonb) returns void language sql security definer set search_path=public as $$

 insert into jobs(kind,dedupe_key,payload) values(k,d,p) on conflict(dedupe_key) do nothing

$$;

create function public.claim_jobs(n integer) returns setof jobs language sql security definer set search_path=public as $$

 update jobs set status='processing',locked_at=now(),lease_id=gen_random_uuid(),attempts=attempts+1 where id in (

 select id from jobs where status='pending' and available_at<=now() order by id for update skip locked limit least(n,20)

 ) returning *

$$;

create function public.notify_incident(i incidents,reason text) returns void language plpgsql security definer set search_path=public as $$

declare recipient jsonb; c contacts; begin

 for recipient in select distinct value from jsonb_array_elements(coalesce(i.policy->'levels'->i.level->'contacts','[]') || case when i.assignee_id is not null then jsonb_build_array(i.assignee_id) else '[]'::jsonb end) loop

 select * into c from contacts where id=(recipient#>>'{}')::uuid and site_id=i.site_id and active;

 if found then perform enqueue('outbound',i.id||':'||reason||':'||c.id||':'||extract(epoch from i.updated_at),

 jsonb_build_object('phone',c.phone,'site_id',i.site_id,'incident_id',i.id,'notification_kind','incident','case_status',i.status,'text',

 format('Incidencia #%s · %s · %s. Dream %s. %s. Responde: RECIBIDO %s, ATENDIENDO %s o SUBSANAR %s descripción. Para adjuntar fotos: CASO %s y luego envía la foto.',

 i.id,i.severity,i.title,coalesce(i.dream_id,'sin especificar'),reason,i.id,i.id,i.id,i.id)));

 end if;

 end loop;

end $$;

create function public.open_incident(s uuid,r uuid,d text,title_text text,asset text,policy_data jsonb,raw jsonb) returns bigint language plpgsql security definer set search_path=public as $$

declare i incidents; begin

 perform pg_advisory_xact_lock(hashtextextended(s::text||coalesce(r::text,'manual')||asset,0));

 select * into i from incidents where site_id=s and rule_id is not distinct from r and asset_key=asset and status<>'resolved' for update;

 if found then update incidents set source_data=raw,source_active=true where id=i.id;return i.id;end if;

 insert into incidents(site_id,rule_id,dream_id,title,asset_key,policy,source_data,severity,next_reminder_at,next_escalation_at)

 values(s,r,d,title_text,asset,policy_data,raw,coalesce(policy_data->>'severity','media'),

 now()+make_interval(mins=>coalesce((policy_data->>'reminder_minutes')::int,15)),

 now()+make_interval(mins=>coalesce((policy_data->>'ack_minutes')::int,10))) returning * into i;

 insert into incident_events(incident_id,actor,action) values(i.id,'system','opened');

 perform notify_incident(i,'Nueva incidencia'); return i.id;

end $$;



create table public.applied_commands(command_id text primary key, incident_id bigint references incidents(id));

alter table applied_commands enable row level security;

create function public.act_incident(case_id bigint,actor_text text,act text,note text,can_approve boolean default false,command_key text default null) returns incidents language plpgsql security definer set search_path=public as $$

declare i incidents; begin

 select * into strict i from incidents where id=case_id for update;

 if command_key is not null then

 if exists(select 1 from applied_commands where command_id=command_key and incident_id=i.id) then return i;end if;

 insert into applied_commands values(command_key,i.id);

 end if;

 if i.status='resolved' and act<>'reopen' then raise exception 'La incidencia ya está cerrada';end if;

 if act in ('ack','start') then

 if i.status='pending_review' then raise exception 'La subsanación está pendiente de aprobación';end if;

 if act='ack' and i.status='in_progress' then return i;end if;

 i.status=case when act='ack' then 'acknowledged' else 'in_progress' end;

 if i.ack_at is null then i.ack_at=now();i.next_escalation_at=now()+make_interval(mins=>(i.policy->>'resolve_minutes')::int);end if;

 elsif act='submit' then

 if length(trim(note))<8 then raise exception 'Describe la subsanación (mínimo 8 caracteres)';end if;

 if coalesce((i.policy->>'photo_required')::boolean,true) and not exists(select 1 from evidence where incident_id=i.id and created_at>=i.created_at) then raise exception 'Adjunta una foto antes de subsanar';end if;

 i.resolution=note;i.submitted_at=now();

 if coalesce((i.policy->>'approval_required')::boolean,true) then i.status='pending_review';

 i.level=least(i.level+1,jsonb_array_length(i.policy->'levels')-1);

 i.next_escalation_at=now()+make_interval(mins=>(i.policy->>'resolve_minutes')::int);

 else i.status='resolved';i.resolved_at=now();end if;

 elsif act='approve' then

 if not can_approve or i.status<>'pending_review' then raise exception 'Requiere supervisor y una subsanación pendiente';end if;

 i.status='resolved';i.resolved_at=now();

 elsif act='reopen' then

 if not can_approve or length(trim(note))<8 then raise exception 'Reapertura requiere supervisor y motivo';end if;

 i.status='open';i.resolved_at=null;i.ack_at=null;i.level=0;i.created_at=now();

 i.next_escalation_at=now()+make_interval(mins=>(i.policy->>'ack_minutes')::int);

 else raise exception 'Acción inválida';end if;

 i.updated_at=now();

 update incidents set status=i.status,ack_at=i.ack_at,submitted_at=i.submitted_at,resolved_at=i.resolved_at,

 resolution=i.resolution,level=i.level,created_at=i.created_at,next_escalation_at=i.next_escalation_at,updated_at=i.updated_at where id=i.id;

 insert into incident_events(incident_id,actor,action,body) values(i.id,actor_text,act,coalesce(note,''));

 if i.status='resolved' then update conversations set mode='bot' where incident_id=i.id;end if;
 perform notify_incident(i,'Estado: '||i.status);

 return i;

end $$;



create function public.tick_incidents() returns integer language plpgsql security definer set search_path=public as $$

declare i incidents;total integer=0;levels integer;next_delay integer;begin

 -- Expired outbound leases are ambiguous: never automatically resend after an unknown Meta outcome.

 update jobs set status=case when kind='outbound' then 'uncertain' else 'pending' end,last_error='Worker lease expired'

 where status='processing' and locked_at<now()-interval '5 minutes';

 for i in select * from incidents where status<>'resolved' and (next_reminder_at<=now() or next_escalation_at<=now()) for update skip locked loop

 levels=jsonb_array_length(i.policy->'levels');

 i.updated_at=now();

 if i.next_escalation_at<=now() and i.level+1<levels then

 i.level=i.level+1;

 next_delay=coalesce((i.policy->'levels'->i.level->>'after_minutes')::int,(i.policy->>'resolve_minutes')::int,60);

 i.next_escalation_at=now()+make_interval(mins=>next_delay);

 insert into incident_events(incident_id,actor,action,body) values(i.id,'system','escalated','Nivel '||i.level);

 perform notify_incident(i,'Escalamiento nivel '||i.level);

 else

 if i.next_reminder_at<=now() then perform notify_incident(i,'Pendiente de subsanar');end if;

 if i.next_escalation_at<=now() then i.next_escalation_at=now()+make_interval(mins=>coalesce((i.policy->>'reminder_minutes')::int,15));end if;

 end if;

 i.next_reminder_at=now()+make_interval(mins=>coalesce((i.policy->>'reminder_minutes')::int,15));

 update incidents set level=i.level,next_reminder_at=i.next_reminder_at,next_escalation_at=i.next_escalation_at,updated_at=i.updated_at where id=i.id;

 total=total+1;

 end loop;return total;

end $$;

-- Service endpoints alone may invoke domain writes.

do $$ declare f record; begin

 for f in select p.oid::regprocedure sig from pg_proc p join pg_namespace n on n.oid=p.pronamespace where n.nspname='public' and p.proname in ('enqueue','claim_jobs','notify_incident','open_incident','act_incident','tick_incidents') loop

 execute format('revoke all on function %s from public, anon, authenticated',f.sig);

 execute format('grant execute on function %s to service_role',f.sig);

 end loop;

end $$;

insert into storage.buckets(id,name,public,file_size_limit,allowed_mime_types) values('evidence','evidence',false,10485760,array['image/jpeg','image/png','image/webp']) on conflict(id) do nothing;
