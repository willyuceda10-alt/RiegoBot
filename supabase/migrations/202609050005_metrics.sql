create table public.metric_mappings(site_id uuid references sites(id),entity text not null,field text not null,unit text not null,scale numeric not null default 1,verified boolean not null default false,primary key(site_id,entity));
alter table metric_mappings enable row level security;
create policy mapping_read on metric_mappings for select to authenticated using(has_site(site_id));
grant select on metric_mappings to authenticated;
revoke insert,update,delete on metric_mappings from authenticated,anon;

