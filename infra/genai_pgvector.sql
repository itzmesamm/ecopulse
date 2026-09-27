-- Optional manual setup for existing Supabase projects already migrated by Alembic.
-- The schema itself is managed by `alembic upgrade head`.

create extension if not exists vector;

create index if not exists ix_log_embeddings_org_id on log_embeddings(org_id);
create index if not exists ix_log_embeddings_embedding_cosine
  on log_embeddings using ivfflat (embedding vector_cosine_ops) with (lists = 100);

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

alter table log_embeddings enable row level security;
create policy log_embeddings_org_isolation on log_embeddings
  for all using (org_id = auth_org_id());

alter table recommendations enable row level security;
create policy recommendations_org_isolation on recommendations
  for all using (org_id = auth_org_id());
