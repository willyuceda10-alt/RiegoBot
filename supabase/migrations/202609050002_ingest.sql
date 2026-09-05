create function public.ingest_batch(batch uuid,collector uuid,rows jsonb) returns void language plpgsql security definer set search_path=public as $$
declare c collectors;r jsonb;begin
 select * into strict c from collectors where id=collector and enabled for update;
 if jsonb_array_length(rows)>500 then raise exception 'Lote demasiado grande';end if;
 if exists(select 1 from batches where id=batch and collector_id<>collector) then raise exception 'Lote ajeno';end if;
 for r in select * from jsonb_array_elements(rows) loop
 if not exists(select 1 from dreams where site_id=c.site_id and dream_id=r->>'dream_id' and enabled) then raise exception 'Dream no autorizado';end if;
 insert into observations(site_id,dream_id,entity,source_key,source_at,data)
 values(c.site_id,r->>'dream_id',r->>'entity',r->>'source_key',(r->>'source_at')::timestamptz,r->'data')
 on conflict(site_id,entity,source_key) do update set data=excluded.data,source_at=excluded.source_at,received_at=now() where excluded.source_at>=observations.source_at;
 end loop;
 insert into batches(id,collector_id) values(batch,collector) on conflict(id) do nothing;
 update collectors set last_seen=now(),last_error=null where id=collector;
end $$;
revoke all on function public.ingest_batch(uuid,uuid,jsonb) from public,anon,authenticated;
grant execute on function public.ingest_batch(uuid,uuid,jsonb) to service_role;

