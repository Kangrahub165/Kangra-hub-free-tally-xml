# Environment Variables Specification
**Kangra Hub Free Tally XML — Configuration Matrix**

This document specifies all environment variables across local development, staging, and production environments, with strict separation between public client-side parameters and private server-side secrets.

---

## 1. Security Classification Rule

> [!CAUTION]
> **NEVER** expose `SUPABASE_SERVICE_ROLE_KEY` or database connection strings to the frontend.
> Any variable prefixed with `NEXT_PUBLIC_` is bundled into client JavaScript and is publicly readable by anyone inspecting browser network traffic.

---

## 2. Frontend Configuration Matrix (`frontend/.env.local` / Netlify)

| Variable Name | Environment | Required | Sensitivity | Default / Example Value | Description |
|---|---|---|---|---|---|
| `NEXT_PUBLIC_API_BASE` | Local | Yes | Public | `http://127.0.0.1:8000` | FastAPI backend URL without trailing slash |
| `NEXT_PUBLIC_API_BASE` | Production | Yes | Public | `https://api.kangrahub.com` or Render URL | Production backend endpoint |
| `NEXT_PUBLIC_SUPABASE_URL` | All | Yes | Public | `https://xyzproject.supabase.co` | Supabase project API URL |
| `NEXT_PUBLIC_SUPABASE_ANON_KEY` | All | Yes | Public | `eyJhbGciOi...` | Supabase anonymous public API key |
| `NEXT_PUBLIC_APP_URL` | Local | Optional | Public | `http://localhost:3000` | Frontend base domain |
| `NEXT_PUBLIC_APP_URL` | Production | Yes | Public | `https://kangrahub.com` | Production canonical frontend domain |
| `NODE_ENV` | All | System | Public | `production` / `development` | Next.js execution mode |

---

## 3. Backend Configuration Matrix (`backend/.env` / Render)

| Variable Name | Environment | Required | Sensitivity | Default / Example Value | Description |
|---|---|---|---|---|---|
| `PORT` | Local | No | Internal | `8000` | Local port binding |
| `PORT` | Production | Auto | Internal | Injected by Render | Render automatically injects `$PORT` |
| `SUPABASE_URL` | All | Yes | Private | `https://xyzproject.supabase.co` | Supabase API connection URL |
| `SUPABASE_KEY` | All | Yes | Private | `eyJhbGciOi...` | Supabase anon key (for client verification) |
| `SUPABASE_SERVICE_ROLE_KEY` | All | Yes | **CRITICAL SECRET** | `eyJhbGciOi...` | Full administrative bypass key for database queries |
| `DATABASE_URL` | Optional | No | **CRITICAL SECRET** | `postgresql://postgres:[pass]@db.xyz.supabase.co:5432/postgres` | Direct PostgreSQL pooling connection string |
| `CORS_ORIGINS` | Local | Yes | Private | `http://localhost:3000,http://127.0.0.1:3000` | Comma-delimited allowed browser origins |
| `CORS_ORIGINS` | Production | Yes | Private | `https://kangrahub.com,https://your-app.netlify.app` | Comma-delimited production frontend domains |
| `MAX_FILE_SIZE_MB` | All | No | Private | `25` | Maximum PDF file upload size accepted in MB |
| `STATEMENT_TIMEOUT_SECONDS` | All | No | Private | `90` | Maximum seconds allowed for single PDF processing |
| `ENVIRONMENT` | All | Yes | Private | `local` / `staging` / `production` | Deployment environment identifier |
| `LOG_LEVEL` | All | No | Private | `INFO` | Logging verbosity (`DEBUG`, `INFO`, `WARNING`, `ERROR`) |
| `TIMEZONE` | All | No | Private | `Asia/Kolkata` | Standard operational timezone for daily quota resets |

---

## 4. Local Development Template Files

### File: `frontend/.env.local`
```env
# Frontend Local Environment
NEXT_PUBLIC_API_BASE=http://127.0.0.1:8000
NEXT_PUBLIC_SUPABASE_URL=https://your-project.supabase.co
NEXT_PUBLIC_SUPABASE_ANON_KEY=your-supabase-anon-key
NEXT_PUBLIC_APP_URL=http://localhost:3000
```

### File: `backend/.env`
```env
# Backend Local Environment
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_KEY=your-supabase-anon-key
SUPABASE_SERVICE_ROLE_KEY=your-supabase-service-role-key
CORS_ORIGINS=http://localhost:3000,http://127.0.0.1:3000
MAX_FILE_SIZE_MB=25
STATEMENT_TIMEOUT_SECONDS=90
ENVIRONMENT=local
LOG_LEVEL=INFO
TIMEZONE=Asia/Kolkata
```

---

## 5. Secret Rotation & Key Hygiene

1. **Service Role Key Security**:
   - Never commit `.env` or `.env.local` to Git repository. Verify `.gitignore` contains `*.env`, `.env.local`, and `.env.*.local`.
   - In the event of an accidental leak, immediately navigate to Supabase Dashboard -> **Settings** -> **API** -> **Rotate secret keys**.
2. **CORS Hardening**:
   - Never set `CORS_ORIGINS=*` in production. Always specify exact canonical domains (`https://kangrahub.com` and Netlify preview domains).
