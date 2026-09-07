-- Store worker_url and worker_secret using Supabase Vault first, then execute this.
-- Never commit real secrets. worker_url = https://PROJECT.supabase.co/functions/v1/worker
create extension if not exists pg_net with schema extensions;
select cron.schedule('riegobot-dispatch','* * * * *',$job$
 select net.http_post(
 url:=(select decrypted_secret from vault.decrypted_secrets where name='riegobot_worker_url'),
 headers:=jsonb_build_object('Content-Type','application/json','x-worker-secret',(select decrypted_secret from vault.decrypted_secrets where name='riegobot_worker_secret')),
 body:='{}'::jsonb
 );
$job$);
