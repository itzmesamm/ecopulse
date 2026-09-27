# EcoPulse Backend Integration and Test Guide

## What the Backend Runs

The backend supports five ingestion inputs: billing, host infrastructure, GPU telemetry, Kubernetes metrics, and operational logs. In development, collectors can generate correlated synthetic data. In live mode they read AWS Cost Explorer, Prometheus (node-exporter, DCGM Exporter, Kubernetes metrics), and Loki. A pipeline run can then perform waste analysis, GPU cross-signal validation, anomaly detection, recommendations, and alert checks.

External providers are configuration-driven. No provider credentials are included in the repository. Real remediation is disabled by default and currently supports only stopping explicitly allowlisted AWS EC2 instances in explicit sandbox/dev/test environments.

## Option A: Local Smoke Test With SQLite

1. Create a local `.env` from `.env.example`. For the local SQLite path set:

   ```dotenv
   DATABASE_URL=sqlite:///./ecopulse-local.db
   APP_ENV=development
   INGESTION_MODE=synthetic
   SYNTHETIC_RECORD_COUNT=100
   INGESTION_ENABLED=false
   PIPELINE_ENABLED=false
   REMEDIATION_ENABLED=false
   OLLAMA_BASE_URL=http://localhost:11434
   OLLAMA_MODEL=llama3.1
   EMBEDDINGS_ENABLED=false
   PIPELINE_RECOMMENDATION_LIMIT=5
   ```

2. Install dependencies and migrate the local schema:

   ```powershell
   .\venv\Scripts\Activate.ps1
   pip install -r requirements.txt
   alembic upgrade head
   ```

3. For offline smoke tests, `EMBEDDINGS_ENABLED=false` avoids model downloads; with Ollama unavailable recommendations use the deterministic local fallback. For grounded LLM recommendations instead, start Ollama:

   ```powershell
   ollama pull llama3.1
   ollama serve
   ```

4. In another terminal start the API:

   ```powershell
   .\venv\Scripts\Activate.ps1
   uvicorn backend.main:app --reload
   ```

5. Preferred: create and log in to a Supabase Auth user at `POST /auth/signup` and `POST /auth/login`. The local database still needs Supabase Auth configured because bearer tokens are verified by Supabase. Use the returned access token as `Authorization: Bearer <token>` on every non-auth request.

   For an offline-only local smoke test, set `APP_ENV=development`, `DEV_AUTH_TOKEN=local-only-test-token`, and `DEV_AUTH_USER_ID=local-test-user`, then create a local organization/profile after migrations:

   ```powershell
   $env:DEV_AUTH_TOKEN = "local-only-test-token"
   $env:DEV_AUTH_USER_ID = "local-test-user"
   .\venv\Scripts\python.exe -c "from backend.db.database import SessionLocal; from backend.db.models import Organization, UserProfile; db=SessionLocal(); org=Organization(id='local-test-org', name='Local test'); db.add(org); db.flush(); db.add(UserProfile(id='local-test-user', org_id=org.id, role='admin')); db.commit(); db.close()"
   ```

   Send `Authorization: Bearer local-only-test-token` and use `local-test-org` as the `org_id`. This branch is ignored whenever `APP_ENV=production`; never deploy that token or enable a fake identity in production.

6. Run a full synthetic collection and analysis pass. For the preferred Supabase login path:

   ```powershell
   $headers = @{ Authorization = "Bearer $($login.access_token)" }
   Invoke-RestMethod -Method Post -Uri "http://localhost:8000/pipeline/run" `
     -Headers $headers -ContentType "application/json" `
     -Body (@{ org_id = $login.org_id; collect = $true } | ConvertTo-Json)
   ```

   The response reports inserted/duplicate source events, waste/GPU/anomaly finding counts, recommendation count, and alerts. The deterministic demo inputs should include a correlated idle host and idle GPU.

7. Check results with authenticated requests:

   ```powershell
   Invoke-RestMethod -Method Get -Uri "http://localhost:8000/waste-analytics/summary?org_id=$($login.org_id)" -Headers $headers
   Invoke-RestMethod -Method Get -Uri "http://localhost:8000/recommendations?org_id=$($login.org_id)" -Headers $headers
   Invoke-RestMethod -Method Get -Uri "http://localhost:8000/greenops/report?org_id=$($login.org_id)" -Headers $headers
   Invoke-RestMethod -Method Post -Uri "http://localhost:8000/remediation/process" `
     -Headers $headers -ContentType "application/json" `
     -Body (@{ org_id = $login.org_id; dry_run = $true } | ConvertTo-Json)
   ```

   Check the `/docs` OpenAPI page for the other routes. Include the required bearer token and organization ID.

## Option B: Your Local PostgreSQL in pgAdmin (No Docker)

This path uses the local PostgreSQL server already registered in pgAdmin. The project `.env` should contain a local URL with host `localhost`, port `5432`, user `postgres`, and database `Ecopulse`; keep the password URL-encoded if it contains reserved characters. Do not paste the password into source files or chat.

1. In pgAdmin, confirm the server is running and the `Ecopulse` database exists. The backend connection was verified against PostgreSQL 18.3.
2. From PowerShell in the `ecopulse` project folder, apply the migrations and seed the database:

   ```powershell
   .\venv\Scripts\Activate.ps1
   .\venv\Scripts\python.exe -m alembic upgrade head
   .\venv\Scripts\python.exe scripts\seed_local_demo.py
   ```

   The seed pass inserts 100 billing rows, 100 host metrics, 100 GPU metrics, 100 Kubernetes metrics, and 100 logs by default. The configured local Ollama model generates up to `PIPELINE_RECOMMENDATION_LIMIT` LLM recommendations per pipeline pass; matching logs are retrieved lexically when embeddings are disabled. It is safe to rerun: billing snapshots deduplicate and active findings/recommendations are reused.

3. Start the API in the same project folder:

   ```powershell
   .\venv\Scripts\python.exe -m uvicorn backend.main:app --reload
   ```

4. In another PowerShell terminal, call the API with the local-only development token configured in `.env`:

   ```powershell
   $headers = @{ Authorization = "Bearer local-ecopulse-test-token" }
   $org = "local-test-org"
   Invoke-RestMethod "http://localhost:8000/health"
   Invoke-RestMethod "http://localhost:8000/waste-analytics/summary?org_id=$org" -Headers $headers
   Invoke-RestMethod "http://localhost:8000/recommendations?org_id=$org" -Headers $headers
   Invoke-RestMethod "http://localhost:8000/greenops/report?org_id=$org" -Headers $headers
   Invoke-RestMethod -Method Post -Uri "http://localhost:8000/pipeline/run" `
     -Headers $headers -ContentType "application/json" `
     -Body (@{ org_id = $org; collect = $false } | ConvertTo-Json)
   ```

   To test the full API collection flow rather than the seeder, pass `collect = $true`. You should see new time-series telemetry rows and duplicate billing snapshots counted as duplicates.

5. In pgAdmin, open the `Ecopulse` database, expand `Schemas > public > Tables`, and refresh. Inspect `billing_records`, `infrastructure_metrics`, `gpu_metrics`, `k8s_metrics`, `operational_logs`, `waste_items`, `gpu_optimization_findings`, `anomaly_findings`, `recommendations`, and `alerts`.

   You can also run this read-only SQL in pgAdmin's Query Tool:

   ```sql
   SELECT 'billing_records' AS table_name, count(*) FROM billing_records WHERE org_id = 'local-test-org'
   UNION ALL SELECT 'infrastructure_metrics', count(*) FROM infrastructure_metrics WHERE org_id = 'local-test-org'
   UNION ALL SELECT 'gpu_metrics', count(*) FROM gpu_metrics WHERE org_id = 'local-test-org'
   UNION ALL SELECT 'k8s_metrics', count(*) FROM k8s_metrics WHERE org_id = 'local-test-org'
   UNION ALL SELECT 'operational_logs', count(*) FROM operational_logs WHERE org_id = 'local-test-org'
   UNION ALL SELECT 'waste_items', count(*) FROM waste_items WHERE org_id = 'local-test-org'
   UNION ALL SELECT 'recommendations', count(*) FROM recommendations WHERE org_id = 'local-test-org';
   ```

The local server does not have pgvector installed. Migrations detect this and use JSON text for embeddings; retrieval falls back to Python cosine similarity. The synthetic smoke test disables embedding-model downloads and uses fallback recommendations, so neither Docker nor Ollama is required.

## Option C: Local PostgreSQL with Docker (Optional)

Start the included PostgreSQL+pgvector, Redis, Ollama, Prometheus, and Loki stack:

```powershell
docker compose up -d postgres redis ollama prometheus loki
docker compose --profile metrics up -d node-exporter
```

For the API running on the Windows host, set:

```dotenv
DATABASE_URL=postgresql://ecopulse:ecopulse-local-only@localhost:55432/ecopulse
REDIS_URL=redis://localhost:6379/0
OLLAMA_BASE_URL=http://localhost:11434
PROMETHEUS_URL=http://localhost:9090
LOKI_URL=http://localhost:3100
```

Then run:

```powershell
alembic upgrade head
uvicorn backend.main:app --reload
```

This uses the standard SQLAlchemy Postgres driver already listed in `requirements.txt`. PostgreSQL enables database-side pgvector similarity search when the `vector` extension is available; otherwise vector extension setup must be enabled in that instance. The Alembic migration creates the extension where permitted and adds the cosine-search index.

The compose password is for local development only; change it and do not reuse it for a deployed environment. Prometheus initially scrapes Prometheus and the optional node-exporter service; GPU/DCGM and Kubernetes scrape targets must be added when those exporters/clusters are available.

## Option D: Existing Supabase Database

1. Back up the database.
2. Compare the existing schema against `migrations/versions/ce298c799493_initial_schema.py`. Only use the baseline stamp if the existing schema actually matches that revision.
3. For a database whose schema matches the pre-Alembic ORM schema, mark that baseline and apply additive revisions:

   ```powershell
   alembic stamp ce298c799493
   alembic upgrade head
   ```

4. If the existing schema differs, do not stamp blindly. Generate/review a migration for the actual schema first. The initial migration is intended for a fresh database; revisions after the baseline add new ingestion tables/indexes.
5. Run `infra/supabase_rls_policies.sql` after migrations. The FastAPI backend uses the service-role Postgres connection; it bypasses RLS, so application bearer validation and organization scoping remain mandatory.
6. For Auth, set `SUPABASE_URL` and `SUPABASE_SERVICE_ROLE_KEY`. Never expose the service-role key in a frontend.

## Live Free-Tier/OSS Providers

- **AWS billing:** configure AWS credentials using the standard AWS SDK chain and `AWS_REGION`. Enable Cost Explorer resource-level data and set `INGESTION_MODE=live`.
- **Prometheus:** set `PROMETHEUS_URL`; export node-exporter, DCGM Exporter, and kube/container metrics. For a protected endpoint, set `PROMETHEUS_BEARER_TOKEN`. Set stable `aws_instance_id`/`instance_id` labels on node samples if billing resource matching is needed.
- **Loki:** set `LOKI_URL`, optionally `LOKI_QUERY`, `LOKI_LOOKBACK_MINUTES`, and `LOKI_BEARER_TOKEN`. Ensure messages include resource/GPU IDs for corroborating waste checks.
- **Ollama:** install Ollama locally, pull the configured model, and set `OLLAMA_BASE_URL` and `OLLAMA_MODEL`. `sentence-transformers` downloads the configured small embedding model the first time logs are indexed; allow that initial network/model download.
- **Slack/Teams/email:** set their webhook variables or SMTP configuration in `.env`. Alert delivery is best-effort, with a 15-minute duplicate suppression window.
- **Celery/Redis:** start Redis, then run a worker and beat process. Scheduled full runs stay disabled unless `PIPELINE_ENABLED=true`:

  ```powershell
  celery -A backend.celery_app.celery_app worker --loglevel=info
  celery -A backend.celery_app.celery_app beat --loglevel=info
  ```

## Safe Remediation Test

Start with `dry_run=true`. Production, staging, unknown, and empty environments require an approver. Only explicit `sandbox`, `development`, `dev`, or `test` resources are eligible for automated action, and only authorized roles can trigger them.

Do not enable real execution until you have a dedicated test AWS account and selected sandbox instance. Set `REMEDIATION_ENABLED=true`, `REMEDIATION_DRY_RUN=false`, `AWS_REGION`, and `REMEDIATION_ALLOWED_INSTANCE_IDS` to the exact instance ID. The only real action currently supported is an EC2 stop; the backend checks AWS state and waits for stopped confirmation. Do not use production resource IDs.

## Automated Tests

Use the repository venv and avoid the real `.env` Postgres URL by setting SQLite for the test process:

```powershell
$env:DATABASE_URL = "sqlite://"
.\venv\Scripts\python.exe -m pytest -q
Remove-Item Env:DATABASE_URL
```

The tests use mocked Supabase identity/provider calls and SQLite tables; they do not call real AWS, Prometheus, Loki, Ollama, Slack, Teams, or SMTP services. Live integrations still need a sandbox smoke test.

## Important Limitations

- Actual savings are not verified from post-remediation billing. Reported values remain estimates.
- The carbon estimator uses regional factors and assumed avoided energy where telemetry is incomplete; it is CCF-inspired, not a complete Cloud Carbon Footprint provider implementation.
- Forecasting uses Prophet when installed and enough history is present, with a deterministic regression fallback otherwise. Measure forecasting error against held-out data before relying on it for budgets.
- Real remediation is limited to one AWS EC2 operation. GPU job scheduling, resizing, deletion, multi-cloud remediators, and rollback remain future work.
- Live AWS/Prometheus/Loki/Supabase/Ollama tests were not run without deployment credentials and services.
