create table public.rule_evaluations(rule_id uuid references rules(id),source_key text,primary key(rule_id,source_key));
alter table rule_evaluations enable row level security;
create function public.evaluate_alert(rule uuid,source text,dream text,asset text,raw jsonb) returns bigint language plpgsql security definer set search_path=public as $$
declare r rules;claimed text;begin
 select * into strict r from rules where id=rule and enabled;
 insert into rule_evaluations values(rule,source) on conflict do nothing returning source_key into claimed;
 if claimed is null then return null;end if;
 return open_incident(r.site_id,r.id,dream,r.name,asset,to_jsonb(r),raw);
end $$;
revoke all on function evaluate_alert(uuid,text,text,text,jsonb) from public,anon,authenticated;
grant execute on function evaluate_alert(uuid,text,text,text,jsonb) to service_role;

