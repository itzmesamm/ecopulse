# EcoPulse Supabase Integration Analysis

## Current Status ✅

Your `.env` file is properly configured with:
- ✅ **PostgreSQL Database URL** (via Supabase pooler)
- ✅ **Supabase URL** configured
- ✅ **ANON_KEY** (for frontend auth)
- ✅ **SERVICE_ROLE_KEY** (for backend)

---

## What's Already in Place

### Backend Setup ✅
- Models defined in `backend/db/models.py`
- SQLAlchemy ORM configured
- All endpoint implementations complete
- CORS middleware enabled
- Auth endpoints for signup/login

### Frontend Setup ✅
- API service with real endpoint calls
- Token management with localStorage
- Environment variables configured
- Error handling with mock fallbacks

---

## What Needs to be Done

### ⚠️ CRITICAL: Backend Database Connection

#### 1. **Update `backend/db/database.py`**
Currently using SQLite. Must switch to PostgreSQL (Supabase):

```python
# CURRENT (SQLite):
DATABASE_URL = "sqlite:///./ecopulse.db"

# SHOULD BE (PostgreSQL):
DATABASE_URL = os.getenv("DATABASE_URL")  # From .env
```

**Location:** [backend/db/database.py](backend/db/database.py)

---

### ⚠️ CRITICAL: Supabase Auth Integration

#### 2. **Verify `backend/db/supabase_client.py`**
Must properly initialize Supabase client:

```python
from supabase import create_client, Client
import os

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY")  # ⚠️ SERVICE_ROLE not ANON

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

def get_supabase():
    return supabase
```

**Location:** [backend/db/supabase_client.py](backend/db/supabase_client.py)

---

### ⚠️ CRITICAL: Frontend Environment

#### 3. **Update `frontend/.env.development`**
Must point to running backend:

```
VITE_API_BASE_URL=http://localhost:8000
VITE_USE_MOCK_DATA=false
```

---

## Step-by-Step Setup Instructions

### Step 1: Verify Backend Database Connection

**Check current database.py:**
```bash
cd backend && cat db/database.py
```

**Expected to see:**
```python
DATABASE_URL = os.getenv("DATABASE_URL")  # Gets from .env
```

**If NOT, update it:**
```python
# Before:
DATABASE_URL = "sqlite:///./ecopulse.db"

# After:
DATABASE_URL = os.getenv("DATABASE_URL")
```

---

### Step 2: Verify Supabase Client Initialization

**Check current supabase_client.py:**
```bash
cat backend/db/supabase_client.py
```

**Expected to see:**
```python
from supabase import create_client

supabase = create_client(
    os.getenv("SUPABASE_URL"),
    os.getenv("SUPABASE_SERVICE_ROLE_KEY")  # NOT ANON_KEY
)
```

**Why SERVICE_ROLE_KEY?**
- ANON_KEY = Frontend only (limited permissions)
- SERVICE_ROLE_KEY = Backend only (full permissions, never expose)

---

### Step 3: Test Database Connection

**Start backend with Supabase:**
```bash
cd ecopulse
uvicorn backend.main:app --reload
```

**Expected in logs:**
```
INFO:     Will watch for changes in these directories: ['C:\Users\nikit\Documents\ecopulse']
INFO:     Uvicorn running on http://localhost:8000
INFO:     Application startup complete.
```

**If you see DATABASE errors:**
```
❌ ERROR: postgresql password authentication failed
→ Check DATABASE_URL in .env has correct credentials
→ Verify Supabase is running and accessible
```

---

### Step 4: Test Supabase Auth Connection

**Run signup endpoint:**
```bash
curl -X POST http://localhost:8000/auth/signup \
  -H "Content-Type: application/json" \
  -d '{
    "email": "test@example.com",
    "password": "Test123!Pass",
    "org_name": "Test Org",
    "full_name": "Test User"
  }'
```

**Expected response:**
```json
{
  "user_id": "...",
  "org_id": "...",
  "role": "admin",
  "note": "Check your email..."
}
```

**If error "Email address is invalid":**
→ Supabase Auth is working but rejecting the email format
→ Use a real email: `yourname+test@gmail.com`

---

### Step 5: Verify Database Tables Created

**Connect to Supabase PostgreSQL:**
```bash
# Use psql or DBeaver
psql postgresql://postgres.lcsmdrhcdrhckayoofhb:password@aws-0-ap-northeast-2.pooler.supabase.com:5432/postgres
```

**Check tables:**
```sql
\dt  -- List all tables

-- Expected tables:
-- organizations
-- user_profiles
-- billing_records
-- gpu_metrics
-- k8s_metrics
-- operational_logs
-- waste_items
-- remediation_actions
-- cloud_providers
```

**If tables don't exist:**
```python
# Backend will auto-create on startup:
# Base.metadata.create_all(bind=engine)
```

---

### Step 6: Test Frontend to Backend

**Ensure .env.development has:**
```
VITE_API_BASE_URL=http://localhost:8000
VITE_USE_MOCK_DATA=false
```

**Start frontend:**
```bash
cd frontend
npm run dev
```

**Test login:**
1. Go to http://localhost:5174
2. Click "Login"
3. Enter the email/password from Step 4
4. Should redirect to dashboard

**Check network tab:**
- Should see POST to `http://localhost:8000/auth/login`
- Response should include `access_token`

---

## Checklist: Getting Everything Connected

- [ ] **Database Connection**
  - [ ] `backend/db/database.py` uses `os.getenv("DATABASE_URL")`
  - [ ] `.env` has `DATABASE_URL=postgresql://...`
  - [ ] Backend starts without database errors
  - [ ] Tables auto-created in Supabase

- [ ] **Supabase Auth**
  - [ ] `backend/db/supabase_client.py` uses SERVICE_ROLE_KEY
  - [ ] `.env` has `SUPABASE_URL` and `SUPABASE_SERVICE_ROLE_KEY`
  - [ ] Signup endpoint creates users in Supabase Auth
  - [ ] Login endpoint validates against Supabase

- [ ] **Frontend to Backend**
  - [ ] `frontend/.env.development` has `VITE_API_BASE_URL=http://localhost:8000`
  - [ ] `USE_MOCK_DATA=false` to use real API
  - [ ] Frontend sends auth token in requests
  - [ ] Login works and redirects to dashboard

- [ ] **API Endpoints**
  - [ ] GET /health returns OK
  - [ ] POST /auth/signup creates organization
  - [ ] POST /auth/login returns access token
  - [ ] GET /waste-analytics/dashboard/stats works with org_id

---

## Common Issues & Solutions

### ❌ "PostgreSQL connection refused"
```
Solution:
1. Verify DATABASE_URL in .env is correct
2. Check Supabase project is active
3. Try: psql <DATABASE_URL> to test directly
4. Check IP whitelist in Supabase (allow your IP)
```

### ❌ "Email address is invalid" in auth
```
Solution:
1. Use a real email: yourname+test@gmail.com
2. Supabase Auth validates email format strictly
3. Or disable email confirmation in Supabase dashboard
```

### ❌ "401 Unauthorized" on protected endpoints
```
Solution:
1. Ensure auth_token is in localStorage after login
2. Check Authorization header is being sent
3. Verify ACCESS_TOKEN format (should be JWT)
4. Check token hasn't expired
```

### ❌ Frontend can't reach backend
```
Solution:
1. Verify backend is running: curl http://localhost:8000/health
2. Check VITE_API_BASE_URL in frontend/.env.development
3. Verify CORS is enabled in backend/main.py
4. Check browser console for CORS errors
```

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────┐
│                     SUPABASE (Cloud)                         │
├─────────────────────────────────────────────────────────────┤
│  ┌──────────────────┐  ┌──────────────────┐                 │
│  │  PostgreSQL DB   │  │   Auth Service   │                 │
│  │                  │  │                  │                 │
│  │ • organizations  │  │ • Users          │                 │
│  │ • users          │  │ • Sessions       │                 │
│  │ • waste_items    │  │ • JWT tokens     │                 │
│  │ • etc...         │  │                  │                 │
│  └──────────────────┘  └──────────────────┘                 │
└─────────────────────────────────────────────────────────────┘
         ↑          ↑                    ↑
         │          │                    │
    (SERVICE_ROLE_KEY via DATABASE_URL) (SERVICE_ROLE_KEY)
         │          │                    │
┌────────┴──────────┴────────────────────┴──────────────────┐
│              FastAPI Backend                               │
│  (http://localhost:8000)                                   │
├────────────────────────────────────────────────────────────┤
│  • /auth/signup     ← Creates Supabase Auth user           │
│  • /auth/login      ← Validates with Supabase Auth        │
│  • /auth/me         ← Gets user from DB                    │
│  • /waste-analytics/* ← Queries PostgreSQL via SQLAlchemy  │
│                                                             │
│  CORS enabled for localhost:5173, localhost:5174           │
└────────────────────────────────────────────────────────────┘
         ↑
    (access_token)
         │
┌────────┴────────────────────────────────────────────────────┐
│              React Frontend (Vite)                           │
│  (http://localhost:5174)                                    │
├─────────────────────────────────────────────────────────────┤
│  • Stores auth_token in localStorage                        │
│  • Sends Authorization: Bearer {token} in requests         │
│  • Displays dashboards and analytics                        │
└─────────────────────────────────────────────────────────────┘
```

---

## Quick Start Commands

```bash
# 1. Install dependencies
cd ecopulse
pip install -r requirements.txt
cd frontend && npm install && cd ..

# 2. Start backend (connects to Supabase)
uvicorn backend.main:app --reload

# 3. In another terminal, start frontend
cd frontend
npm run dev

# 4. Test in browser
# Frontend: http://localhost:5174
# Backend Docs: http://localhost:8000/docs
```

---

## Key Environment Variables

| Variable | Location | Use | Example |
|----------|----------|-----|---------|
| `DATABASE_URL` | Backend | PostgreSQL connection | `postgresql://...@supabase.com:5432/postgres` |
| `SUPABASE_URL` | Backend + Frontend | Supabase project URL | `https://lcsmdrhcdrhckayoofhb.supabase.co` |
| `SUPABASE_ANON_KEY` | Frontend only | Limited client auth | `eyJhbGciOi...` |
| `SUPABASE_SERVICE_ROLE_KEY` | Backend only | Full admin auth | `eyJhbGciOi...` |
| `VITE_API_BASE_URL` | Frontend | Backend URL | `http://localhost:8000` |
| `VITE_USE_MOCK_DATA` | Frontend | Use mock or real API | `false` (use real) |

---

## Next Steps

1. **Verify database.py** uses PostgreSQL from .env
2. **Verify supabase_client.py** uses SERVICE_ROLE_KEY
3. **Confirm .env.development** has correct API base URL
4. **Run backend** and check for connection errors
5. **Test signup/login** endpoints
6. **Test frontend** login flow
7. **Monitor Supabase dashboard** for created users/data

All endpoints are ready—just need to verify the Supabase connections are properly configured!
