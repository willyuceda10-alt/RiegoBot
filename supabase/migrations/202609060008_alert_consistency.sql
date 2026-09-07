-- Evaluate only the observation revision that is still persisted as current.
-- A delayed batch must not create a new alert after a newer normal sample.
create or replace function public.evaluate_alert(rule uuid,source text,dream text,asset text,raw jsonb)
returns bigint language plpgsql security definer set search_path=public as $$
declare r rules; claimed text; sample observations; reading numeric; begin
  select * into strict r from rules where id=rule and enabled;
  if r.kind='support' or r.entity is distinct from raw->>'entity'
    or (r.dream_id is not null and r.dream_id<>dream) then return null; end if;
  select * into sample from observations
    where site_id=r.site_id and dream_id=dream and entity=r.entity
      and source_key=raw->>'source_key' for share;
  if not found or sample.source_at is distinct from (raw->>'source_at')::timestamptz
    or sample.data is distinct from raw->'data'
    or sample.source_at>now()+interval '1 minute'
    or sample.source_at<now()-make_interval(mins=>r.stale_minutes) then return null; end if;
  if jsonb_typeof(sample.data->r.field) not in ('number','string') then return null; end if;
  begin
    reading=(sample.data->>r.field)::numeric;
  exception when invalid_text_representation or numeric_value_out_of_range then return null;
  end;
  if reading is null or reading::text in ('NaN','Infinity','-Infinity')
    or not (case r.operator when 'gt' then reading>r.value when 'lt' then reading<r.value else reading=r.value end)
    then return null; end if;
  insert into rule_evaluations values(rule,source) on conflict do nothing returning source_key into claimed;
  if claimed is null then return null; end if;
  return open_incident(r.site_id,r.id,dream,r.name,asset,to_jsonb(r),raw);
end $$;

-- Persist the WhatsApp message -> case identity through closure and worker retries.
create function public.open_support_incident(rule uuid,message_id text,phone text,dream text,title_text text)
returns bigint language plpgsql security definer set search_path=public as $$
declare r rules; case_id bigint; begin
  if nullif(trim(message_id),'') is null then raise exception 'Mensaje requerido'; end if;
  perform pg_advisory_xact_lock(hashtextextended('support:'||message_id,0));
  select incident_id into case_id from applied_commands where command_id=message_id;
  if found then return case_id; end if;
  select * into strict r from rules where id=rule and enabled and kind='support';
  if not exists(select 1 from contacts where site_id=r.site_id and contacts.phone=open_support_incident.phone and active)
    then raise exception 'Contacto no autorizado'; end if;
  case_id=open_incident(r.site_id,r.id,dream,title_text,'manual:'||message_id,to_jsonb(r),
    jsonb_build_object('message_id',message_id,'requester_phone',phone));
  insert into applied_commands(command_id,incident_id) values(message_id,case_id);
  return case_id;
end $$;
revoke all on function public.open_support_incident(uuid,text,text,text,text) from public,anon,authenticated;
grant execute on function public.open_support_incident(uuid,text,text,text,text) to service_role;
