-- Schedule the SQL state machine locally; dispatch requires the private worker URL/secret.
create extension if not exists pg_cron with schema pg_catalog;
select cron.schedule('riegobot-incidents','* * * * *','select public.tick_incidents()');
