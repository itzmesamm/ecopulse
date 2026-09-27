# EcoPulse

AI-powered FinOps and GreenOps backend with tenant-scoped APIs, five-source ingestion, waste and anomaly analytics, forecasting, grounded recommendations, guarded remediation, alerts, and GreenOps reporting.

## Setup

1. **Create a virtual environment and install dependencies**

   ```
   python -m venv venv
   # Windows:
   venv\Scripts\activate
   # macOS/Linux:
   source venv/bin/activate

   pip install -r requirements.txt
   ```

   Optional local integration stack: `docker compose up -d postgres redis ollama prometheus loki` (see [BACKEND_TESTING.md](BACKEND_TESTING.md)).

2. **Set up Supabase**
   - Create a free project at [supabase.com](https://supabase.com)
   - Get your connection string: Settings → Database → Connection string (URI tab). Postgres is the recommended shared database; SQLite is fine for local-only tests.
   - Get your API keys: Settings → API → Project URL, anon key, service_role key

3. **Configure environment**

   ```
   copy .env.example .env      # Windows
   cp .env.example .env        # macOS/Linux
   ```

   Fill in `DATABASE_URL`, `SUPABASE_URL`, `SUPABASE_ANON_KEY`, `SUPABASE_SERVICE_ROLE_KEY`.

4. **Run the server**

   ```
   alembic upgrade head
   uvicorn backend.main:app --reload --reload-dir backend
   ```

   Visit http://localhost:8000/docs. Schema changes are versioned under `migrations/`; the API no longer mutates production schema during import/startup.

   For an existing database created by the pre-Alembic backend, take a backup and compare the tables/columns with the deployed ORM schema. If it matches, mark the baseline and apply the additive revisions with `alembic stamp ce298c799493` followed by `alembic upgrade head`. Do not stamp a database whose schema has drifted; prepare a reviewed migration first.

5. **Apply Row Level Security**
   Copy `infra/supabase_rls_policies.sql` into Supabase's SQL Editor and run it once after migrations. The backend still enforces tenant scope independently; service-role connections bypass database RLS by design.

For the full step-by-step local SQLite, local Postgres, existing Supabase, free-tier provider, Celery, and sandbox-remediation test workflow, see [BACKEND_TESTING.md](BACKEND_TESTING.md).

6. **Try it out**
   - `POST /auth/signup` with an email, password, and org_name → creates your org + admin user, returns `org_id`
   - `POST /auth/login` → returns a Supabase access token
   - Send `Authorization: Bearer <access_token>` on every non-auth API request. The backend derives the user's organization and role from the verified token's profile; a caller-supplied `org_id` must match.
   - In local development, `INGESTION_MODE=synthetic` enables reproducible-shape demo data. `POST /ingest?org_id=<your org id>` persists billing, host, GPU, Kubernetes, and log records.
   - For live data, set `INGESTION_MODE=live`, configure AWS Cost Explorer access plus `PROMETHEUS_URL` (node-exporter, DCGM Exporter, and Kubernetes metrics) and `LOKI_URL` (Loki logs). AWS resource-level cost data must be enabled for the account.
   - To schedule ingestion, configure Redis, set `INGESTION_ENABLED=true`, then run a Celery worker and beat process. Scheduled ingestion is disabled by default.
   - To schedule the complete collect → analyze → recommend → alert cycle, set `PIPELINE_ENABLED=true` and run Celery worker + beat. You can run analysis immediately with `POST /pipeline/run` and `{"org_id":"<your org id>","collect":true}`.
   - Remediation defaults to dry-run. Real execution requires `REMEDIATION_ENABLED=true`, `REMEDIATION_DRY_RUN=false`, AWS credentials/region, and the exact sandbox EC2 IDs in `REMEDIATION_ALLOWED_INSTANCE_IDS`. Only stop actions execute; unsupported actions/resources fail closed. Production, staging, and unknown environment labels require human approval.
   - Check the database tables `billing_records`, `infrastructure_metrics`, `gpu_metrics`, `k8s_metrics`, `operational_logs`, and `ingestion_records`.

## Project structure

```
ecopulse/
├── backend/
│   ├── main.py                 # FastAPI app entrypoint
│   ├── db/
│   │   ├── database.py         # engine/session setup, reads DATABASE_URL
│   │   ├── models.py           # SQLAlchemy models (org/auth, ingestion, analytics, recommendations)
│   │   └── supabase_client.py  # Supabase client for Auth calls
│   ├── api/
│   │   └── auth.py             # /auth/signup, /auth/login
│   └── ingestion/
│       ├── billing_collector.py
│       ├── infrastructure_collector.py
│       ├── gpu_telemetry_collector.py
│       ├── k8s_collector.py
│       ├── operational_logs_collector.py
│       └── persist.py          # normalizes and idempotently persists collector output
├── infra/
│   └── supabase_rls_policies.sql
├── requirements.txt
└── .env.example
```

## Troubleshooting

- **`uvicorn: command not found`** — dependencies weren't installed into the active venv. Run `pip install -r requirements.txt` again and confirm with `pip show uvicorn`.
- **`psycopg2` build errors on Windows** — you're using `psycopg2-binary` (prebuilt wheel), so this should be rare; if it happens, ensure you're on a 64-bit Python 3.11+.
- **RLS blocking backend writes** — the backend uses the service-role key, which bypasses RLS by design. If writes fail after applying RLS, double check `SUPABASE_SERVICE_ROLE_KEY` (not the anon key) is what's in `DATABASE_URL`'s implied connection / used by `supabase_client.py`.
