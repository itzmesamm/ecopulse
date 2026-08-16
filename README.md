# EcoPulse

AI-powered FinOps and GreenOps platform. This repo currently contains:

- **Org / Auth foundation** — multi-tenant organizations, Supabase Auth-backed signup/login
- **Layer 1 — Data Ingestion** — billing, GPU telemetry, Kubernetes metrics, operational logs
  (synthetic data for now, tagged and persisted per-organization)

Layers 2–5 (analytics, GenAI recommendations, remediation, dashboards) will be added incrementally on top of this foundation.

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

2. **Set up Supabase**
   - Create a free project at [supabase.com](https://supabase.com)
   - Get your connection string: Settings → Database → Connection string (URI tab)
   - Get your API keys: Settings → API → Project URL, anon key, service_role key

3. **Configure environment**
   ```
   copy .env.example .env      # Windows
   cp .env.example .env        # macOS/Linux
   ```
   Fill in `DATABASE_URL`, `SUPABASE_URL`, `SUPABASE_ANON_KEY`, `SUPABASE_SERVICE_ROLE_KEY`.

4. **Run the server**
   ```
   uvicorn backend.main:app --reload
   ```
   Visit http://localhost:8000/docs — tables are created automatically on startup.

5. **Apply Row Level Security**
   Copy `infra/supabase_rls_policies.sql` into Supabase's SQL Editor and run it once.

6. **Try it out**
   - `POST /auth/signup` with an email, password, and org_name → creates your org + admin user, returns `org_id`
   - `POST /ingest?org_id=<that id>` → pulls synthetic Layer 1 data and persists it
   - Check the Supabase Table Editor — `billing_records`, `gpu_metrics`, `k8s_metrics`, `operational_logs` should have rows

## Project structure

```
ecopulse/
├── backend/
│   ├── main.py                 # FastAPI app entrypoint
│   ├── db/
│   │   ├── database.py         # engine/session setup, reads DATABASE_URL
│   │   ├── models.py           # SQLAlchemy models (org/auth + Layer 1 tables)
│   │   └── supabase_client.py  # Supabase client for Auth calls
│   ├── api/
│   │   └── auth.py             # /auth/signup, /auth/login
│   └── ingestion/
│       ├── billing_collector.py
│       ├── gpu_telemetry_collector.py
│       ├── k8s_collector.py
│       ├── operational_logs_collector.py
│       └── persist.py          # writes collector output to the DB
├── infra/
│   └── supabase_rls_policies.sql
├── requirements.txt
└── .env.example
```

## Troubleshooting

- **`uvicorn: command not found`** — dependencies weren't installed into the active venv. Run `pip install -r requirements.txt` again and confirm with `pip show uvicorn`.
- **`psycopg2` build errors on Windows** — you're using `psycopg2-binary` (prebuilt wheel), so this should be rare; if it happens, ensure you're on a 64-bit Python 3.11+.
- **RLS blocking backend writes** — the backend uses the service-role key, which bypasses RLS by design. If writes fail after applying RLS, double check `SUPABASE_SERVICE_ROLE_KEY` (not the anon key) is what's in `DATABASE_URL`'s implied connection / used by `supabase_client.py`.
