-- Apply contact authorization before LIMIT so recent unrelated cases cannot
-- hide an older case assigned to the person asking for PENDIENTES.
create function public.contact_incidents(contact uuid,max_rows integer default 15)
returns setof incidents language sql stable security definer set search_path=public as $$
  select i.* from incidents i join contacts c on c.site_id=i.site_id
  where c.id=contact and c.active and i.status<>'resolved'
    and (
      c.role in ('supervisor','jefe','mantenimiento','admin')
      or i.assignee_id=c.id
      or i.source_data->>'requester_phone'=c.phone
      or exists (
        select 1 from jsonb_array_elements(coalesce(i.policy->'levels','[]'::jsonb)) as policy_level(value)
        where (policy_level.value->'contacts') ? c.id::text
      )
    )
  order by i.created_at desc,i.id desc
  limit greatest(1,least(coalesce(max_rows,15),50))
$$;
revoke all on function public.contact_incidents(uuid,integer) from public,anon,authenticated;
grant execute on function public.contact_incidents(uuid,integer) to service_role;
