-- Layer 3 GenAI RAG setup for Supabase Postgres.
-- Run once in Supabase SQL Editor after the base tables exist.

create extension if not exists vector;

create table if not exists log_embeddings (
  id text primary key,
  org_id text not null references organizations(id),
  content text not null,
  embedding vector(384) not null,
  source_ref text references operational_logs(id),
  source_type text not null default 'operational_log',
  created_at timestamp default now()
);

create index if not exists ix_log_embeddings_org_id on log_embeddings(org_id);

alter table billing_records add column if not exists team text;
alter table billing_records add column if not exists owner text;

create or replace function match_log_embeddings(
  query_embedding vector(384),
  match_count int,
  target_org_id text
)
returns table(content text, source_ref text, similarity float)
language sql
stable
as $$
  select
    le.content,
    le.source_ref,
    1 - (le.embedding <=> query_embedding) as similarity
  from log_embeddings le
  where le.org_id = target_org_id
  order by le.embedding <=> query_embedding
  limit match_count;
$$;

alter table recommendations add column if not exists waste_finding_id text references waste_items(id);
alter table recommendations add column if not exists explanation text;
alter table recommendations add column if not exists dollar_savings double precision default 0;
alter table recommendations add column if not exists carbon_savings_kg double precision;
alter table recommendations add column if not exists suggested_action text;
alter table recommendations add column if not exists status text not null default 'pending';

alter table log_embeddings enable row level security;
create policy log_embeddings_org_isolation on log_embeddings
  for all using (org_id = auth_org_id());

alter table recommendations enable row level security;
create policy recommendations_org_isolation on recommendations
  for all using (org_id = auth_org_id());
