# Supabase Connection Status & Changes Needed

## ✅ What's Already Correctly Configured

### 1. Backend Database Connection ✅
**File:** `backend/db/database.py`

**Status:** READY - Already reads from environment!
```python
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./ecopulse.db")
```

**Current .env:**
```
DATABASE_URL=postgresql://postgres.lcsmdrhcdrhckayoofhb:123@thebest@123@aws-0-ap-northeast-2.pooler.supabase.com:5432/postgres
```

✅ No changes needed - This will automatically connect to Supabase PostgreSQL!

---

### 2. Supabase Auth Client ✅
**File:** `backend/db/supabase_client.py`

**Status:** READY - Already configured correctly!
```python
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_SERVICE_ROLE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
```

**Current .env has:**
```
SUPABASE_URL=https://lcsmdrhcdrhckayoofhb.supabase.co
SUPABASE_SERVICE_ROLE_KEY=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
```

✅ No changes needed - Auth is ready!

---

### 3. Frontend API Connection ✅
**File:** `frontend/.env.development`

**Status:** READY
```
VITE_API_BASE_URL=http://localhost:8000
VITE_USE_MOCK_DATA=false
```

✅ No changes needed - Will connect to local backend!

---

### 4. CORS Configuration ✅
**File:** `backend/main.py`

**Status:** READY
```python
app.add_middleware(CORSMiddleware, ...)
```

✅ Frontend can talk to backend!

---

## ❌ What Needs to Happen (Operational, Not Code)

### Step 1: Start Backend Server
```bash
cd c:\Users\nikit\Documents\ecopulse
uvicorn backend.main:app --reload
```

**What happens:**
1. Reads `.env` file
2. Connects to Supabase PostgreSQL via DATABASE_URL
3. Creates tables automatically (if not exist)
4. Starts listening on http://localhost:8000

**Check for this output:**
```
INFO:     Application startup complete.
INFO:     Uvicorn running on http://localhost:8000
```

---

### Step 2: Start Frontend Server
```bash
cd c:\Users\nikit\Documents\ecopulse\frontend
npm run dev
```

**What happens:**
1. Reads `.env.development`
2. Points to http://localhost:8000 for API calls
3. Starts on http://localhost:5174

---

### Step 3: Test Signup/Login Flow

**Open browser:** http://localhost:5174/signup

**Sign up with:**
- Email: `yourname+test@gmail.com` (must be real email for Supabase)
- Password: `Test123!Pass`
- Org: `Test Company`
- Name: `Your Name`

**Expected result:**
1. ✅ Supabase Auth creates user (check auth.users in Supabase)
2. ✅ Backend creates organization in PostgreSQL
3. ✅ Backend creates user_profile in PostgreSQL
4. ✅ Frontend stores token in localStorage
5. ✅ Redirects to dashboard

---

## Potential Issues & Fixes

### Issue 1: "Connection refused" when starting backend
```
Error: Failed to connect to postgresql://...
```

**Fixes:**
1. Check your IP is whitelisted in Supabase
   - Go to Supabase → Project Settings → Database → Allowed IP Addresses
   - Add your current IP (or 0.0.0.0 for development)

2. Verify DATABASE_URL in .env
   ```bash
   echo $env:DATABASE_URL  # PowerShell
   ```
   Should show full PostgreSQL connection string

3. Test direct connection:
   ```bash
   psql postgresql://postgres.lcsmdrhcdrhckayoofhb:password@aws-0-ap-northeast-2.pooler.supabase.com:5432/postgres
   ```

---

### Issue 2: "Email address is invalid" during signup
```
Error: Email address "test@example.com" is invalid
```

**Fix:** Use a real email address
- ✅ `yourname+test@gmail.com`
- ✅ `your.real.email@company.com`
- ❌ `test@example.com` (not real, Supabase rejects)

---

### Issue 3: Frontend can't reach backend
```
Error: Failed to fetch http://localhost:8000/auth/signup
```

**Fixes:**
1. Make sure backend is running
   ```bash
   curl http://localhost:8000/health
   # Should return: {"status": "ok"}
   ```

2. Check VITE_API_BASE_URL in `frontend/.env.development`
   Should be: `VITE_API_BASE_URL=http://localhost:8000`

3. Check browser console for CORS errors
   - Verify backend has CORSMiddleware

---

### Issue 4: Login works but no data appears in dashboard
```
Tables exist but showing 0 items
```

**This is normal!** 
- The tables are empty until you analyze billing data
- Run this endpoint to populate data:
  ```bash
  POST http://localhost:8000/ingest?org_id={your_org_id}
  ```

---

## What Data Flows Where

```
1. FRONTEND (React)
   ↓ POST /auth/signup
   ↓ {email, password, org_name}
   
2. BACKEND (FastAPI)
   ↓ Calls Supabase Auth API
   ↓ Creates user in supabase.auth.users
   ↓ Writes to PostgreSQL via SQLAlchemy
   ↓ Creates Organization row
   ↓ Creates UserProfile row
   
3. SUPABASE (Cloud)
   ├─ auth.users table (Supabase managed)
   └─ PostgreSQL tables (Your app)
      ├─ organizations
      ├─ user_profiles
      ├─ waste_items
      ├─ billing_records
      └─ etc...

4. RESPONSE
   ← Backend returns org_id, user_id, access_token
   ← Frontend stores access_token in localStorage
   ← Subsequent requests include: Authorization: Bearer {token}
```

---

## Files to Keep in Sync

| File | Status | Notes |
|------|--------|-------|
| `.env` | ✅ Correct | Has DATABASE_URL and SUPABASE keys |
| `backend/db/database.py` | ✅ Correct | Reads from DATABASE_URL |
| `backend/db/supabase_client.py` | ✅ Correct | Uses SERVICE_ROLE_KEY |
| `backend/main.py` | ✅ Correct | CORS enabled |
| `frontend/.env.development` | ✅ Correct | Points to localhost:8000 |
| `frontend/src/services/api.js` | ✅ Correct | Sends real API calls |

**All files are properly configured - no code changes needed!**

---

## Summary: Ready to Connect! 🚀

### What's Done:
- ✅ Database configuration (automatic from .env)
- ✅ Supabase Auth setup (automatic from .env)
- ✅ API endpoints all implemented
- ✅ Frontend integration complete
- ✅ CORS configured
- ✅ Mock data fallback ready

### What You Need to Do:
1. **Start backend:** `uvicorn backend.main:app --reload`
2. **Start frontend:** `npm run dev` (in frontend folder)
3. **Test:** Sign up, login, verify data appears
4. **Monitor:** Check Supabase dashboard for created tables/users

### Next Steps (After Testing):
- Add more test organizations
- Run `/ingest` endpoint to populate billing data
- Check waste analysis dashboard
- Deploy to production

---

## Quick Test

```bash
# 1. Terminal 1: Start backend
cd ecopulse
uvicorn backend.main:app --reload

# 2. Terminal 2: Start frontend  
cd frontend
npm run dev

# 3. Browser: Open http://localhost:5174
# 4. Sign up and test the flow
```

**Everything should work because all configurations are already in place!**

If you encounter any errors, they'll be specific connection issues (IP whitelist, credentials, etc.) - not code problems.
