-- Run this in Supabase SQL Editor AFTER the backend has created tables
-- (i.e. after Base.metadata.create_all() has run once against your Supabase DB).
--
-- What this does: enforces "you can only see rows belonging to your own org"
-- at the database level, so even if application code has a bug, one
-- company's data can never leak into another's.

create or replace function auth_org_id()
returns text
language sql
stable
as $$
  select org_id from user_profiles where id = auth.uid()::text
$$;

alter table billing_records enable row level security;
alter table gpu_metrics enable row level security;
alter table k8s_metrics enable row level security;
alter table operational_logs enable row level security;
alter table user_profiles enable row level security;

create policy org_isolation_billing on billing_records
  for all using (org_id = auth_org_id());

create policy org_isolation_gpu on gpu_metrics
  for all using (org_id = auth_org_id());

create policy org_isolation_k8s on k8s_metrics
  for all using (org_id = auth_org_id());

create policy org_isolation_logs on operational_logs
  for all using (org_id = auth_org_id());

create policy org_isolation_profiles on user_profiles
  for select using (org_id = auth_org_id());

-- Note: the FastAPI backend connects using the SERVICE ROLE key, which
-- BYPASSES RLS by design. RLS here is the safety net for any future path
-- where the frontend queries Supabase directly with a user's own token
-- (e.g. via supabase-js), not a replacement for org_id filtering in the
-- backend code, which is still required.
