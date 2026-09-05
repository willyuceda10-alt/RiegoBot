create function public.query_readings(s uuid,e text,d text default null,today_only boolean default false) returns setof observations language sql stable security definer set search_path=public as $$
 select o.* from observations o join sites s1 on s1.id=o.site_id
 where o.site_id=s and o.entity=e and (d is null or o.dream_id=d)
 and (not today_only or (o.source_at at time zone s1.timezone)::date=(now() at time zone s1.timezone)::date)
 order by o.source_at desc limit 1000
$$;
revoke all on function query_readings(uuid,text,text,boolean) from public,anon,authenticated;
grant execute on function query_readings(uuid,text,text,boolean) to service_role;
