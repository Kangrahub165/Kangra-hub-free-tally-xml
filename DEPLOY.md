# Kangra Hub – Free Tally XML
## Complete Step-by-Step Production Deployment Guide

> **Authoritative Deployment Manual**  
> **Repository:** `https://github.com/Kangrahub165/Kangra-hub-free-tally-xml`  
> **Frontend:** Next.js 14 (App Router) on **Netlify Free Tier**  
> **Backend:** FastAPI (Python 3.12 / Uvicorn) on **Render Web Service**  
> **Database & Auth:** PostgreSQL (13 Tables, RLS, Stored Procedures) on **Supabase**  
> **Last Verified:** September 2026

---

## Fill These Values During Deployment

Keep this reference sheet handy while deploying. Only record safe, non-sensitive URLs and identifiers here.

```text
================================================================================
DEPLOYMENT REFERENCE SHEET — SAFE PUBLIC VALUES ONLY
(DO NOT WRITE PASSWORDS, SECRET KEYS, OR PRIVATE CREDENTIALS IN THIS FILE!)
================================================================================
1. GITHUB_REPOSITORY_URL     = https://github.com/Kangrahub165/Kangra-hub-free-tally-xml.git
2. GITHUB_BRANCH             = main

3. SUPABASE_PROJECT_REF      = YOUR_SUPABASE_PROJECT_REF (e.g. abcdefghijklmno)
4. SUPABASE_PROJECT_URL      = https://YOUR_SUPABASE_PROJECT_REF.supabase.co

5. RENDER_SERVICE_NAME       = kangra-hub-backend
6. RENDER_BACKEND_URL        = https://YOUR_RENDER_SERVICE.onrender.com
7. RENDER_API_BASE_URL       = https://YOUR_RENDER_SERVICE.onrender.com/api

8. NETLIFY_SITE_NAME        = kangra-hub-tally-xml
9. NETLIFY_SITE_URL         = https://YOUR_NETLIFY_SITE.netlify.app

10. ADMIN_ACCOUNT_EMAIL      = admin@tallyxml.in
11. CUSTOM_DOMAIN (OPTIONAL) = YOUR_CUSTOM_DOMAIN (e.g. tally.kangrahub.com)
================================================================================
```

> [!CAUTION]
> **CRITICAL SECURITY DIRECTIVE ON SECRET KEYS & CREDENTIALS:**
> - **NEVER** write your Supabase Secret Key (`service_role` key), database passwords, admin passwords, or SMTP secrets inside this file or any file in your Git repository.
> - **Private Secrets** must **ONLY** be entered directly into the **Render Dashboard** (under Web Service -> Environment).
> - **Public/Publishable Keys** are entered into the **Netlify Dashboard** (under Site Configuration -> Environment Variables).
> - Netlify and client-side JavaScript must **NEVER** receive secret keys.

---

## Table of Contents

1. [Important Deployment Architecture](#1-important-deployment-architecture)
2. [What You Need Before Starting](#2-what-you-need-before-starting)
3. [Project Directory & File Structure](#3-project-directory--file-structure)
4. [Master Secrets & Environment Variables Specification](#4-master-secrets--environment-variables-specification)
5. [Supabase Key Model & Project Variable Mapping](#5-supabase-key-model--project-variable-mapping)
6. [Deployment Order Overview](#6-deployment-order-overview)
7. [STEP 1: Verify Project Locally](#7-step-1-verify-project-locally)
8. [STEP 2: Prepare & Push GitHub Repository](#8-step-2-prepare--push-github-repository)
9. [STEP 3: Supabase Complete Production Setup](#9-step-3-supabase-complete-production-setup)
10. [STEP 4: Deploy Backend to Render](#10-step-4-deploy-backend-to-render)
11. [STEP 5: Configure Backend Environment Variables on Render](#11-step-5-configure-backend-environment-variables-on-render)
12. [STEP 6: Deploy Frontend to Netlify (Free Plan)](#12-step-6-deploy-frontend-to-netlify-free-plan)
13. [STEP 7: Configure Netlify Environment Variables](#13-step-7-configure-netlify-environment-variables)
14. [STEP 8: Configure Supabase Production Auth & Redirect URLs](#14-step-8-configure-supabase-production-auth--redirect-urls)
15. [STEP 9: Configure & Verify Production Admin Account](#15-step-9-configure--verify-production-admin-account)
16. [STEP 10: Verify Frontend → Backend → Supabase Connection](#16-step-10-verify-frontend--backend--supabase-connection)
17. [STEP 11: End-to-End Production Testing Checklist](#17-step-11-end-to-end-production-testing-checklist)
18. [STEP 12: Remove Local Development URLs (No Localhost in Production)](#18-step-12-remove-local-development-urls-no-localhost-in-production)
19. [STEP 13: Optional Custom Domain Setup & DNS](#19-step-13-optional-custom-domain-setup--dns)
20. [Render Free-Tier Limitations & Keep-Alive Strategy](#20-render-free-tier-limitations--keep-alive-strategy)
21. [File Storage Architecture & Ephemeral Disk Warning](#21-file-storage-architecture--ephemeral-disk-warning)
22. [Continuous Deployment (Automatic Git Deploys)](#22-continuous-deployment-automatic-git-deploys)
23. [Rollback & Disaster Recovery](#23-rollback--disaster-recovery)
24. [Production Security Checklist](#24-production-security-checklist)
25. [Comprehensive Troubleshooting Guide](#25-comprehensive-troubleshooting-guide)
26. [Deployment Security Audit & Architectural Notes](#26-deployment-security-audit--architectural-notes)
27. [Final Deployment Checklist](#27-final-deployment-checklist)

---

## 1. Important Deployment Architecture

Kangra Hub Free Tally XML uses a decoupled, modern three-tier architecture:

```text
                             +-------------------+
                             |  GitHub Repository |
                             |    (origin/main)   |
                             +---------+---------+
                                       |
                   +-------------------+-------------------+
                   |                                       |
                   v (Automatic CD)                        v (Automatic CD)
        +---------------------+                 +---------------------+
        |   Netlify Hosting   |                 |    Render Service   |
        | Frontend Tier (CDN) |                 |     Backend Tier    |
        | Next.js 14 App Router|                |  FastAPI + Python 3 |
        +----------+----------+                 +----------+----------+
                   |                                       |
                   |          HTTPS REST API Calls         |
                   +-------------------------------------->|
                   |   (NEXT_PUBLIC_API_URL + Bearer JWT)   |
                   |                                       |
                   |                                       |
                   v (Supabase JS Client)                  v (Supabase Python Service Role)
         +-------------------------------------------------------------+
         |                       Supabase Platform                     |
         |  - PostgreSQL Database (13 base tables, RLS, Quota Engine)  |
         |  - GoTrue Auth (JWT verification, Sign in, Password resets) |
         +-------------------------------------------------------------+
```

### Responsibility Matrix

| Service | Hosting Role | Technology | Cost / Plan | Key Responsibilities |
|---|---|---|---|---|
| **GitHub** | Version Control & Source of Truth | Git | Free | Triggers automated deployments to Netlify and Render on `git push origin main`. |
| **Netlify** | Frontend Application | Next.js 14, React 18, Tailwind CSS | Free Plan | Serves pre-rendered pages, interactive converter studio, admin UI, client state, and responsive assets. |
| **Render** | Backend API Engine | Python 3.12, FastAPI, Uvicorn, pdfplumber, pypdf | Free Web Service (or Starter $7/mo) | Bank statement extraction, 38-bank signature matching, balance math validation, double-entry Tally XML generation, 11-column Excel export. |
| **Supabase** | Managed Database & Auth | PostgreSQL 15, GoTrue Auth | Free Tier (500 MB DB) | User authentication, user profiles, daily quota tracking (`usage_daily`), audit logs, bank parsers, and conversion job metadata. |

---

## 2. What You Need Before Starting

Ensure you have created the following free accounts before beginning the deployment process:

1. **GitHub Account**: Access to push to repository `Kangrahub165/Kangra-hub-free-tally-xml`.
2. **Supabase Account** ([supabase.com](https://supabase.com)): Free tier provides 2 free projects, 500 MB database storage, and 50,000 monthly active auth users.
3. **Render Account** ([render.com](https://render.com)): Free tier provides 750 free instance hours per month for web services.
4. **Netlify Account** ([netlify.com](https://netlify.com)): Free tier provides 100 GB/month bandwidth, 300 build minutes/month, and unlimited edge deploys.
5. **Computer with Git, Node.js, and Python**:
   - Node.js `v20.x` or `v22.x` (LTS recommended)
   - Python `3.11.x` or `3.12.x`
   - Git CLI configured with your credentials

> [!NOTE]
> **Free Tier Honest Limits:**
> - Render Free Web Services automatically spin down after **15 minutes of inactivity**. The first visitor request afterwards takes ~50 to 70 seconds to boot up. (A free UptimeRobot ping solves this; see Section 20).
> - Render Free Web Services provide **512 MB of RAM**. Statement processing is configured with 1 worker to prevent memory spikes.
> - Netlify Free Plan is ideal for Next.js frontend hosting and will easily handle thousands of visitors per month.

---

## 3. Project Directory & File Structure

Here is the exact layout of the repository and what gets deployed where:

```text
Kangra-hub-free-tally-xml/
│
├── frontend/                          --> DEPLOYED TO NETLIFY
│   ├── .env.local                     --> (Local only - Excluded by .gitignore - NEVER push to Git)
│   ├── next.config.js                 --> Next.js build & image configuration
│   ├── package.json                   --> Dependencies (Next 14, React 18, Supabase-js, Tailwind)
│   ├── tailwind.config.js             --> Design system & typography tokens
│   ├── tsconfig.json                  --> TypeScript configuration
│   ├── public/                        --> Static assets (logo.webp, icons, manifests)
│   └── src/                           --> Application source code
│       ├── app/                       --> Next.js 14 App Router pages (44 routes)
│       │   ├── page.tsx               --> Homepage
│       │   ├── convert/page.tsx       --> User Bank Statement Converter Studio
│       │   ├── dashboard/page.tsx     --> User Dashboard & Quota Counter
│       │   ├── login/page.tsx         --> User Login
│       │   ├── signup/page.tsx        --> User Registration
│       │   ├── forgot-password/       --> Password reset request
│       │   ├── admin/                 --> Admin Command Center
│       │   │   ├── page.tsx           --> Admin Overview & KPI Cards
│       │   │   ├── convert/page.tsx   --> Admin Converter (Unlimited & Bank Override)
│       │   │   ├── login/page.tsx     --> Admin Dedicated Login (admin@tallyxml.in)
│       │   │   ├── reset-password/    --> Admin Password Recovery
│       │   │   ├── users/             --> Admin User Management
│       │   │   ├── parsers/           --> Admin 38 Bank Parsers
│       │   │   └── settings/          --> Admin System Settings & Mode
│       │   └── ...                    --> Legal, FAQs, support, contact pages
│       ├── components/                --> Reusable UI components & modals
│       └── lib/                       --> Supabase client & API fetch wrappers
│
├── backend/                           --> DEPLOYED TO RENDER
│   ├── .env                           --> (Local only - Excluded by .gitignore - NEVER push to Git)
│   ├── requirements.txt               --> Python dependencies (FastAPI, uvicorn, pdfplumber, pypdf, supabase)
│   ├── main.py                        --> FastAPI entry point (FastAPI app, CORS, lifespan, router includes)
│   ├── Dockerfile                     --> Container definition (alternative for Docker deployments)
│   ├── app/                           --> Backend application logic
│   │   ├── api/                       --> REST routers (/conversions, /admin, /auth, /banks, /system)
│   │   ├── core/                      --> Config (config.py), security (security.py), db helpers
│   │   ├── parsers/                   --> 38 Indian bank parser implementations
│   │   ├── pdf/                       --> Layout extraction engine & password decryptor
│   │   ├── transactions/              --> Running balance math validator & ledger classifier
│   │   ├── tally/                     --> Tally Prime / Tally 9 XML generation engine
│   │   └── utils/                     --> Temp file cleaner & logging utilities
│   └── tests/                         --> Pytest test suite (23 test modules)
│
├── database/                          --> EXECUTED IN SUPABASE SQL EDITOR
│   ├── supabase_complete.sql          --> AUTHORITATIVE 1,150-line full idempotent setup script
│   ├── promote_admin.sql              --> Helper SQL to promote user to ADMIN
│   └── README.md                      --> Database architecture documentation
│
├── Sample pdf/                        --> LOCAL TEST ASSETS (Not deployed to web)
├── test_fixtures/                     --> Pytest fixtures (Not deployed to web)
├── run as local host/                 --> Windows batch files for local development
├── .gitignore                         --> Strict exclusions for secrets, temp files, and caches
├── .env.example                       --> Example environment variable keys
├── Master.xml                         --> Reference Tally XML format
├── SAMPLE.xml                         --> Reference Tally XML format
└── DEPLOY.md                          --> THIS FILE (Authoritative deployment guide)
```

---

## 4. Master Secrets & Environment Variables Specification

Inspect the strict separation between public variables safe for the browser and private server-side secrets:

### Frontend Environment Variables (Netlify)

| Variable | Used By | Required | Public / Secret | Where to Configure |
|---|---|---|---|---|
| `NEXT_PUBLIC_API_URL` | Frontend API client | **YES** | **Public** | Netlify Site Configuration |
| `NEXT_PUBLIC_SUPABASE_URL` | Frontend Supabase client | **YES** | **Public** | Netlify Site Configuration |
| `NEXT_PUBLIC_SUPABASE_ANON_KEY` | Frontend Supabase client | **YES** | **Public** | Netlify Site Configuration |
| `NEXT_PUBLIC_SITE_URL` | Frontend SEO & canonical tags | **YES** | **Public** | Netlify Site Configuration |
| `NEXT_PUBLIC_SITE_NAME` | Frontend branding | No | **Public** | Netlify Site Configuration |
| `NODE_VERSION` | Netlify build container | No | **Public** | Netlify Site Configuration |

### Backend Environment Variables (Render)

| Variable | Used By | Required | Public / Secret | Where to Configure |
|---|---|---|---|---|
| `APP_ENV` | Backend settings | **YES** | Internal | Render Web Service Environment |
| `APP_NAME` | Backend settings | No | Internal | Render Web Service Environment |
| `SUPABASE_URL` | Backend Supabase service | **YES** | Internal | Render Web Service Environment |
| `SUPABASE_ANON_KEY` | Backend Supabase client | **YES** | Internal | Render Web Service Environment |
| `SUPABASE_SERVICE_ROLE_KEY` | Backend database operations | **YES** | **CRITICAL SECRET** | Render Web Service Environment ONLY |
| `FRONTEND_URL` | Backend CORS & system redirects | **YES** | Internal | Render Web Service Environment |
| `CORS_ORIGINS` | Backend CORSMiddleware | **YES** | Internal | Render Web Service Environment |
| `ADMIN_EMAIL` | Backend auth & notifications | **YES** | Internal | Render Web Service Environment |
| `ADMIN_RECOVERY_EMAIL` | Backend recovery notifications | No | Internal | Render Web Service Environment |
| `SITE_MODE` | Backend system settings | No | Internal | Render Web Service Environment |
| `FREE_DAILY_PAGE_LIMIT` | Backend quota engine | No | Internal | Render Web Service Environment |
| `MAX_UPLOAD_SIZE_MB` | Backend upload validator | No | Internal | Render Web Service Environment |
| `MAX_PAGES_PER_FILE` | Backend upload validator | No | Internal | Render Web Service Environment |
| `PAGE_PRICE_INR` | Backend pricing engine | No | Internal | Render Web Service Environment |
| `PAYMENT_UPI_ID` | Backend payment settings | No | Internal | Render Web Service Environment |
| `DEFAULT_TIMEZONE` | Backend quota calendar | No | Internal | Render Web Service Environment |
| `MAINTENANCE_MODE` | Backend access control | No | Internal | Render Web Service Environment |
| `ALLOW_NEW_SIGNUPS` | Backend auth controller | No | Internal | Render Web Service Environment |
| `BUY_COFFEE_ENABLED` | Backend developer support | No | Internal | Render Web Service Environment |
| `BUY_COFFEE_UPI_ID` | Backend developer support | No | Internal | Render Web Service Environment |
| `FILE_RETENTION_MINUTES` | Backend temp file cleanup | No | Internal | Render Web Service Environment |

---

## 5. Supabase Key Model & Project Variable Mapping

Supabase uses a distinct API-key security model. Understanding this prevents catastrophic security misconfigurations:

### The Two Supabase Keys

1. **Publishable Key (Client/Browser Safe)**:
   - In Supabase Dashboard, this is called the **Publishable Key** (modern format starts with `sb_publishable_...`, or legacy anon JWT).
   - This key is designed to be public and bundled into frontend JavaScript. It only grants permissions allowed by PostgreSQL **Row Level Security (RLS)** policies.
2. **Secret Key (Server-Side ONLY)**:
   - In Supabase Dashboard, this is called the **Secret Key** (modern format starts with `sb_secret_...`, or legacy service_role JWT).
   - This key **completely bypasses Row Level Security (RLS)**. It gives full administrative superuser access to all tables, auth records, and stored procedures.

### Exact Mapping to This Project's Codebase

> [!IMPORTANT]
> **DO NOT RENAME ENVIRONMENT VARIABLE KEYS IN THE SOURCE CODE.**  
> The codebase has been inspected and expects these exact names:

```text
+-------------------------------------------------------------------------------+
| SUPABASE KEY TYPE    | CODEBASE VARIABLE NAME         | WHERE IT GOES        |
+----------------------+--------------------------------+----------------------+
| 1. Publishable Key   | NEXT_PUBLIC_SUPABASE_ANON_KEY  | Netlify Dashboard    |
|                      | SUPABASE_ANON_KEY              | Render Dashboard     |
+----------------------+--------------------------------+----------------------+
| 2. Secret Key        | SUPABASE_SERVICE_ROLE_KEY      | Render Dashboard ONLY|
+----------------------+--------------------------------+----------------------+
```

> [!CAUTION]
> **NEVER** set `NEXT_PUBLIC_SUPABASE_SERVICE_ROLE_KEY`.  
> Any variable starting with `NEXT_PUBLIC_` is readable by every visitor inspecting web traffic. Placing the secret key in the frontend gives any user total control over your entire database.

---

## 6. Deployment Order Overview

Follow these steps in exact numerical order. This ensures dependent URLs (such as the Render API endpoint) exist before configuring the services that rely on them (such as Netlify):

```text
  [STEP 1] Verify Project Locally (Build frontend & start backend)
     │
  [STEP 2] Prepare & Push Clean GitHub Repository
     │
  [STEP 3] Setup Supabase (Run supabase_complete.sql & configure auth)
     │
  [STEP 4] Deploy Backend to Render (Create Web Service)
     │
  [STEP 5] Configure Backend Environment Variables on Render
     │
  [STEP 6] Deploy Frontend to Netlify (Connect GitHub repo)
     │
  [STEP 7] Configure Netlify Environment Variables (Point to Render URL)
     │
  [STEP 8] Configure Supabase Production Auth Redirect URLs
     │
  [STEP 9] Promote Production Admin (admin@tallyxml.in)
     │
  [STEP 10] Verify End-to-End Browser Connection
     │
  [STEP 11] Perform Production Testing Checklist
     │
  [STEP 12] Verify Zero Localhost URLs in Production Bundle
     │
  [STEP 13] (Optional) Configure Custom Domain & SSL
```

---

## 7. STEP 1: Verify Project Locally

Before deploying to the cloud, make sure the project compiles and starts on your local machine without any errors.

### 1. Frontend Build Verification

Open a terminal or command prompt:

```bash
cd "d:\KANGRA HUB FREE TALLY XML\frontend"
npm install
npm run build
```

*(Note for Windows PowerShell users: if script security blocks `npm`, run `npm.cmd run build`)*

**What a successful build looks like:**
- The terminal displays `✓ Compiled successfully`.
- `Generating static pages (44/44)` completes.
- All 44 routes (including `/`, `/convert`, `/dashboard`, `/admin/*`) show green circular icons `○ (Static)`.
- Zero compile or TypeScript errors.

### 2. Backend Startup Verification

Open a second terminal window:

```bash
cd "d:\KANGRA HUB FREE TALLY XML\backend"

# (Optional) Create and activate a Python virtual environment:
# On Windows:
python -m venv venv
.\venv\Scripts\activate

# On Linux / macOS:
# python3 -m venv venv
# source venv/bin/activate

# Install requirements
pip install -r requirements.txt

# Start the FastAPI development server
python -m uvicorn main:app --host 127.0.0.1 --port 8000
```

**What a successful backend startup looks like:**
- Terminal displays:
  ```text
  [INFO] [kangra_hub] Starting Kangra Hub Free Tally XML Engine...
  [INFO] Application startup complete.
  [INFO] Uvicorn running on http://127.0.0.1:8000
  ```

### 3. Verify Health Endpoint

Open your browser or run:

```bash
curl http://127.0.0.1:8000/health
```

Expected JSON response:
```json
{
  "status": "healthy",
  "app": "Kangra Hub Free Tally XML",
  "site_mode": "FREE",
  "app_env": "development",
  "supabase_connected": true,
  "timestamp": "2026-..."
}
```

Interactive OpenAPI documentation is also viewable at `http://127.0.0.1:8000/docs`.

---

## 8. STEP 2: Prepare & Push GitHub Repository

Render and Netlify will pull your source code directly from GitHub and rebuild automatically every time you push code.

### 1. Verify Git Status & Ensure Secrets are Excluded

Run:

```bash
cd "d:\KANGRA HUB FREE TALLY XML"
git status
```

> [!CAUTION]
> Inspect the output carefully! Ensure that **NONE** of the following files appear under "Untracked files" or "Changes to be committed":
> - `backend/.env`
> - `frontend/.env.local`
> - `.env`
> - Any `.pem`, `.key`, or database credentials
> 
> The project's `.gitignore` file already excludes these patterns. Verify by running:
> ```bash
> git check-ignore -v backend/.env frontend/.env.local
> ```
> Both files should return a matching line from `.gitignore`.

### 2. Stage, Commit, and Push Final Code

```bash
git add .
git commit -m "Production release candidate with deployment documentation"
git push origin main
```

### 3. Confirm on GitHub

Open your browser and navigate to:
`https://github.com/Kangrahub165/Kangra-hub-free-tally-xml`

Verify that:
1. The branch `main` shows your latest commit message.
2. The `frontend/` and `backend/` directories are present.
3. No `.env` or `.env.local` files exist in the repository file browser.

---

## 9. STEP 3: Supabase Complete Production Setup

The entire database architecture (13 base tables, RLS security policies, 38 Indian bank parsers, 216 detection signatures, atomic quota stored procedures, and triggers) is packaged into a single authoritative file: `database/supabase_complete.sql`.

### 1. Create a Fresh Supabase Project

1. Go to [https://supabase.com/dashboard](https://supabase.com/dashboard) and sign in.
2. Click **New project**.
3. Select your organization.
4. Fill in project details:
   - **Name**: `kangra-hub-tally-xml`
   - **Database Password**: Choose a strong, random password (store it securely in your password manager).
   - **Region**: Choose **South Asia (Mumbai) - ap-south-1** (Crucial for fastest Indian banking API latency).
   - **Pricing Plan**: **Free**.
5. Click **Create new project** and wait ~90 seconds for provisioning.

### 2. Retrieve Your Supabase API Keys

Once the project is active:
1. Click the **Project Settings** (gear icon) at the bottom of the left sidebar.
2. Click **API** under Configuration.
3. Copy these values:
   - **Project URL**: (e.g. `https://YOUR_SUPABASE_PROJECT_REF.supabase.co`)
   - **Project API Keys -> Publishable Key (`anon` / `public`)**: Copy this value. You will paste it into Netlify (`NEXT_PUBLIC_SUPABASE_ANON_KEY`) and Render (`SUPABASE_ANON_KEY`).
   - **Project API Keys -> Secret Key (`service_role` / `secret`)**: Copy this value. You will paste it **ONLY** into Render (`SUPABASE_SERVICE_ROLE_KEY`).

### 3. Execute `database/supabase_complete.sql`

1. In the Supabase left sidebar, click the **SQL Editor** icon (`>_`).
2. Click **+ New query**.
3. Open [`database/supabase_complete.sql`](file:///d:/KANGRA%20HUB%20FREE%20TALLY%20XML/database/supabase_complete.sql) on your computer, copy its entire contents (1,150+ lines), and paste it into the Supabase SQL Editor.
4. Click the green **Run** button (or press `Ctrl + Enter`).
5. Wait ~5 to 10 seconds. You will see **Success. No rows returned** or query results.

### 4. Verify Database Execution

In the SQL Editor, create a new query tab and run these verification queries:

```sql
-- 1. Verify all 13 core tables exist
SELECT count(*) AS total_tables 
FROM information_schema.tables 
WHERE table_schema = 'public' 
  AND table_name IN (
    'system_settings', 'profiles', 'user_access', 'usage_daily',
    'bank_parsers', 'bank_signatures', 'conversion_jobs', 'user_ledgers',
    'bank_ledger_configs', 'transactions', 'ledger_mappings',
    'audit_logs', 'notifications'
  );
-- Expected result: 13

-- 2. Verify 38 Indian banks are seeded
SELECT count(*) AS registered_banks FROM public.bank_parsers;
-- Expected result: 38

-- 3. Verify bank signatures are active
SELECT count(*) AS bank_signatures FROM public.bank_signatures;
-- Expected result: >= 216

-- 4. Verify RLS is enabled on all tables
SELECT tablename, rowsecurity 
FROM pg_tables 
WHERE schemaname = 'public' 
ORDER BY tablename;
-- Expected result: rowsecurity = true for all 13 tables

-- 5. Verify atomic quota function exists
SELECT routine_name 
FROM information_schema.routines 
WHERE routine_schema = 'public' AND routine_name = 'check_and_record_usage';
-- Expected result: check_and_record_usage
```

If all 5 queries return the expected counts, your database is 100% properly configured.

---

## 10. STEP 4: Deploy Backend to Render

Now deploy the Python FastAPI backend engine to Render.

### 1. Create a Web Service on Render

1. Open [https://dashboard.render.com](https://dashboard.render.com) and sign in.
2. Click the blue **New +** button in the top right, and select **Web Service**.
3. Select **Build and deploy from a Git repository** and click **Next**.
4. Connect your GitHub account and choose the repository:  
   `Kangrahub165/Kangra-hub-free-tally-xml`.
5. Configure the service settings:

| Render Setting | Exact Value to Enter | Explanation |
|---|---|---|
| **Name** | `kangra-hub-backend` | Your service name in Render |
| **Region** | **Singapore** (or Frankfurt) | Lowest latency for India |
| **Branch** | `main` | Production Git branch |
| **Root Directory** | `backend` | **CRITICAL!** Must be set to `backend` so Render looks inside the backend folder |
| **Runtime** | **Python 3** | Native Python runtime |
| **Build Command** | `pip install --upgrade pip && pip install -r requirements.txt` | Upgrades pip and installs all 16 libraries |
| **Start Command** | `uvicorn main:app --host 0.0.0.0 --port $PORT --workers 1` | Binds to Render's dynamic port with 1 worker |
| **Instance Type** | **Free** | 512 MB RAM / 0.1 CPU |

> [!IMPORTANT]
> **Why `--workers 1` on Render Free Tier?**  
> Render Free Tier provides 512 MB RAM. PDF parsing libraries (`pdfplumber`) build in-memory character coordinate trees. Running 1 worker ensures that statement conversions do not exceed the 512 MB ceiling.

---

## 11. STEP 5: Configure Backend Environment Variables on Render

In the same Render Web Service creation screen (or under the **Environment** tab):

1. Scroll down to **Environment Variables**.
2. Click **Add Environment Variable** for each key listed below.

### Render Backend Environment Variables Table

| Key | Value to Enter | Secret? | Purpose |
|---|---|---|---|
| `APP_ENV` | `production` | No | Enables production mode |
| `APP_NAME` | `Kangra Hub Free Tally XML` | No | Branding in API responses |
| `SUPABASE_URL` | `https://YOUR_SUPABASE_PROJECT_REF.supabase.co` | No | Your Supabase project URL |
| `SUPABASE_ANON_KEY` | `YOUR_SUPABASE_PUBLISHABLE_KEY` | No | Supabase Publishable / Anon Key |
| `SUPABASE_SERVICE_ROLE_KEY` | `YOUR_SUPABASE_SECRET_KEY` | **CRITICAL SECRET** | Supabase Secret / Service Role Key (Backend DB access) |
| `FRONTEND_URL` | `https://YOUR_NETLIFY_SITE.netlify.app` *(update in Step 8)* | No | Production frontend origin |
| `CORS_ORIGINS` | `https://YOUR_NETLIFY_SITE.netlify.app,http://localhost:3000` | No | Comma-separated allowed frontend origins |
| `ADMIN_EMAIL` | `admin@tallyxml.in` | No | Primary administrator email |
| `ADMIN_RECOVERY_EMAIL` | `YOUR_RECOVERY_EMAIL@domain.com` | No | Secondary backup recovery email |
| `SITE_MODE` | `FREE` | No | System mode (`FREE` or `PAID`) |
| `FREE_DAILY_PAGE_LIMIT` | `50` | No | Free user daily page allowance |
| `MAX_UPLOAD_SIZE_MB` | `25` | No | Maximum PDF file upload size |
| `MAX_PAGES_PER_FILE` | `2500` | No | Safety ceiling for statement pages |
| `PAGE_PRICE_INR` | `2.0` | No | Optional price per page for paid mode |
| `PAYMENT_UPI_ID` | `YOUR_UPI_ID@bank` | No | Manual UPI ID for Section 129 payments |
| `DEFAULT_TIMEZONE` | `Asia/Kolkata` | No | Quotas reset at 00:00 midnight IST |
| `MAINTENANCE_MODE` | `false` | No | Platform availability toggle |
| `ALLOW_NEW_SIGNUPS` | `true` | No | User registration toggle |
| `BUY_COFFEE_ENABLED` | `true` | No | Voluntary developer support toggle |
| `BUY_COFFEE_UPI_ID` | `YOUR_UPI_ID@bank` | No | Voluntary support UPI handle |
| `FILE_RETENTION_MINUTES` | `60` | No | Lifespan for temporary processing files |

*(Optional SMTP Email Variables — only configure if you want custom transactional emails instead of Supabase defaults:)*
- `SMTP_HOST`: `YOUR_SMTP_HOST`
- `SMTP_PORT`: `587`
- `SMTP_USER`: `YOUR_SMTP_USER`
- `SMTP_PASSWORD`: `YOUR_SMTP_PASSWORD`
- `SMTP_FROM_EMAIL`: `noreply@yourdomain.com`
- `SMTP_FROM_NAME`: `Kangra Hub Free Tally XML`

### 3. Deploy & Note Backend URL

1. Click **Create Web Service**.
2. Render will initiate the build. Watch the log output:
   - Git repository cloned.
   - `pip install` completes.
   - `Uvicorn running on http://0.0.0.0:10000` appears.
3. At the top of the page, Render displays your live URL, for example:
   `https://kangra-hub-backend.onrender.com`
4. Copy this URL into your deployment reference sheet.
5. Test it in your browser:
   `https://kangra-hub-backend.onrender.com/health`
   You should see:
   ```json
   {"status":"healthy","app":"Kangra Hub Free Tally XML","site_mode":"FREE","supabase_connected":true}
   ```

---

## 12. STEP 6: Deploy Frontend to Netlify (Free Plan)

Deploy the Next.js 14 frontend using Netlify's Free Tier.

### 1. Connect GitHub to Netlify

1. Open [https://app.netlify.com](https://app.netlify.com) and log in.
2. On the team overview page, click **Add new site** -> **Import an existing project**.
3. Click **GitHub** and authorize Netlify.
4. Select the repository: `Kangrahub165/Kangra-hub-free-tally-xml`.

### 2. Configure Build Settings

Netlify will detect Next.js. Verify or enter the following settings:

| Netlify Setting | Value to Enter | Explanation |
|---|---|---|
| **Branch to deploy** | `main` | Production branch |
| **Base directory** | `frontend` | **CRITICAL!** Root folder of the Next.js application |
| **Build command** | `npm run build` | Next.js production build command |
| **Publish directory** | `frontend/.next` (or `.next`) | Managed automatically by `@netlify/plugin-nextjs` |

*(Leave functions directory blank)*

---

## 13. STEP 7: Configure Netlify Environment Variables

Before clicking Deploy, configure your production environment variables in Netlify:

1. Click **Add environment variables** (or go to **Site configuration** -> **Environment variables** after creating the site).
2. Add the following variables:

### Netlify Frontend Environment Variables Table

| Key | Required | Value to Enter | Explanation |
|---|---|---|---|
| `NEXT_PUBLIC_API_URL` | **YES** | `https://YOUR_RENDER_SERVICE.onrender.com/api` | **CRITICAL**: Your Render backend URL with `/api` suffix (No trailing slash after `/api`) |
| `NEXT_PUBLIC_SUPABASE_URL` | **YES** | `https://YOUR_SUPABASE_PROJECT_REF.supabase.co` | Your Supabase project URL |
| `NEXT_PUBLIC_SUPABASE_ANON_KEY` | **YES** | `YOUR_SUPABASE_PUBLISHABLE_KEY` | Your Supabase Publishable / Anon Key |
| `NEXT_PUBLIC_SITE_URL` | **YES** | `https://YOUR_NETLIFY_SITE.netlify.app` *(or custom domain)* | Canonical domain of your frontend |
| `NEXT_PUBLIC_SITE_NAME` | No | `Kangra Hub Free Tally XML` | Public platform name |
| `NODE_VERSION` | No | `20.10.0` | Pins the Node.js LTS version |

> [!CAUTION]
> **CRITICAL URL FORMAT NOTICE:**  
> In `frontend/src/lib/api.ts`, API requests are made using `${API_BASE}/auth/login`, `${API_BASE}/conversions/upload`, etc.  
> Therefore, `NEXT_PUBLIC_API_URL` **MUST** include `/api` at the end:  
> `https://<your-render-service>.onrender.com/api`  
> Do NOT omit `/api`. Do NOT add a trailing slash (e.g. do NOT write `.../api/`).

### 3. Deploy Frontend

1. Click **Deploy kangra-hub-free-tally-xml** (or **Deploy site**).
2. Netlify will build the Next.js project. You can inspect the deploy logs:
   - Dependencies installed (`npm install`).
   - Next.js build runs (`next build`).
   - 44 static routes generated.
   - Deployed to Netlify CDN.
3. Once deployed, Netlify will assign a subdomain, such as:
   `https://kangra-hub-tally-xml.netlify.app`
4. Copy this Netlify URL into your deployment reference sheet.

---

## 14. STEP 8: Configure Supabase Production Auth & Redirect URLs

Now that your frontend Netlify domain is known, inform Supabase where authentication callbacks and password reset links are permitted to redirect.

### 1. Update Supabase URL Configuration

1. Open your [Supabase Dashboard](https://supabase.com/dashboard).
2. In the left navigation, click the **Authentication** icon (person with key).
3. Under **Configuration**, click **URL Configuration**.
4. Set **Site URL** to your production Netlify address:
   ```text
   https://YOUR_NETLIFY_SITE.netlify.app
   ```
5. Under **Redirect URLs**, click **Add URL** and add the following allowed callback paths:
   ```text
   https://YOUR_NETLIFY_SITE.netlify.app/**
   https://YOUR_NETLIFY_SITE.netlify.app/dashboard
   https://YOUR_NETLIFY_SITE.netlify.app/login
   https://YOUR_NETLIFY_SITE.netlify.app/convert
   https://YOUR_NETLIFY_SITE.netlify.app/admin
   https://YOUR_NETLIFY_SITE.netlify.app/admin/reset-password
   http://localhost:3000/**
   http://localhost:3000/dashboard
   http://localhost:3000/login
   http://localhost:3000/convert
   http://localhost:3000/admin
   http://localhost:3000/admin/reset-password
   ```
   *(Keeping `localhost:3000` allows you to continue testing locally without breaking production).*
6. Click **Save**.

### 2. Update Render Backend CORS with Netlify URL

Return to Render:
1. Open your `kangra-hub-backend` service on Render.
2. Go to the **Environment** tab.
3. Update `FRONTEND_URL` to:
   `https://YOUR_NETLIFY_SITE.netlify.app`
4. Update `CORS_ORIGINS` to:
   `https://YOUR_NETLIFY_SITE.netlify.app,http://localhost:3000`
5. Click **Save Changes**. Render will automatically trigger a brief redeployment to apply the new environment variables.

---

## 15. STEP 9: Configure & Verify Production Admin Account

The authoritative production administrator account for this platform is:

```text
Email: admin@tallyxml.in
Role:  ADMIN (Full unlimited privileges, bank overrides, system settings)
```

No passwords are ever hardcoded in the codebase. Admin access is granted by creating the user and promoting them securely via Supabase.

### 1. Register the Administrator Account

1. Visit your live production site:
   `https://YOUR_NETLIFY_SITE.netlify.app/signup`
2. Fill out the registration form:
   - **Full Name**: `System Administrator`
   - **Email Address**: `admin@tallyxml.in`
   - **Password**: Create a strong administrator password (at least 8 characters).
3. Click **Create Free Account**.

*(If you have Email Confirmation turned ON in Supabase, check your inbox and click the confirmation link, or confirm it in the Supabase Dashboard -> Authentication -> Users -> click user -> "Confirm Email").*

### 2. Promote to Authoritative Admin in Supabase

1. Open your Supabase Dashboard -> **SQL Editor**.
2. Open a **New Query** tab and execute:

```sql
SELECT public.promote_user_to_admin('admin@tallyxml.in');
```

**Expected output:**
```text
Success: User admin@tallyxml.in (<uuid>) has been promoted to ADMIN with UNLIMITED access.
```

### 3. Verify Admin Privileges in Supabase

Run this verification query in the SQL Editor:

```sql
SELECT 
    p.user_id,
    p.full_name,
    p.email,
    p.role,
    ua.unlimited,
    ua.access_type
FROM public.profiles p
LEFT JOIN public.user_access ua ON ua.user_id = p.user_id
WHERE LOWER(p.email) = LOWER('admin@tallyxml.in');
```

**Expected row returned:**
- `role`: `ADMIN`
- `unlimited`: `true`
- `access_type`: `UNLIMITED`

### 4. Test Production Admin Access

1. Open your browser and go to:
   `https://YOUR_NETLIFY_SITE.netlify.app/admin/login`
2. Enter `admin@tallyxml.in` and your admin password.
3. Click **Sign In to Admin Console**.
4. You should be redirected immediately to `/admin`.
5. Verify that the top navigation bar displays the **`ADMIN • UNLIMITED`** badge.
6. Click **Admin Converter** (`/admin/convert`) — verify that file uploads state *"Unlimited Quota Active"*.

---

## 16. STEP 10: Verify Frontend → Backend → Supabase Connection

Open your browser's Developer Tools (`F12` or `Ctrl + Shift + I` / `Cmd + Option + I`) and select the **Network** tab.

### Verification Flow

```text
Browser User
    │
    ▼ (1) Open https://YOUR_NETLIFY_SITE.netlify.app
    Check DevTools: All JS chunks and Tailwind CSS load with HTTP 200 OK.
    │
    ▼ (2) Open https://YOUR_NETLIFY_SITE.netlify.app/login
    Sign in with a user account.
    Check DevTools:
    - POST to https://YOUR_RENDER_SERVICE.onrender.com/api/auth/login (or Supabase Auth)
    - Response: HTTP 200 OK with Bearer token.
    │
    ▼ (3) Navigate to /dashboard
    Check DevTools:
    - GET to https://YOUR_RENDER_SERVICE.onrender.com/api/usage/summary
    - Response: HTTP 200 OK with {"daily_limit": 50, "pages_used_today": 0, "pages_remaining": 50}
    │
    ▼ (4) Navigate to /convert and upload a test PDF
    Check DevTools:
    - POST to https://YOUR_RENDER_SERVICE.onrender.com/api/conversions/upload
    - Response: HTTP 200 OK with detected bank and extracted transactions.
```

If all 4 steps succeed, your three tiers are communicating cleanly without CORS, routing, or credential errors.

---

## 17. STEP 11: End-to-End Production Testing Checklist

Execute each check in your live production environment:

### A. Public Website
- [ ] Visit `https://YOUR_NETLIFY_SITE.netlify.app/` — homepage renders hero, features, and bank logos.
- [ ] Visit `/supported-banks` — renders list of all supported Indian banks.
- [ ] Visit `/how-it-works` — renders 3-step walkthrough guide.
- [ ] Visit `/faq` — accordion items expand and collapse.
- [ ] Visit `/contact` — support inquiry form renders.
- [ ] Visit `/terms` and `/privacy` — legal terms render properly.

### B. User Authentication
- [ ] Visit `/signup` — register a new test user (e.g. `testuser@example.com`).
- [ ] User receives confirmation or logs in successfully.
- [ ] Visit `/login` — test user logs in with credentials.
- [ ] Session persists on page reload.
- [ ] User profile shows in dashboard navigation.
- [ ] Logout button logs user out and clears session token.

### C. Password Recovery
- [ ] Visit `/forgot-password` — enter registered email and submit.
- [ ] Supabase dispatches password recovery email.
- [ ] Link in email opens production domain `/admin/reset-password` or recovery flow.
- [ ] New password can be saved and used to sign in.

### D. User Converter & Daily Quota
- [ ] Visit `/dashboard` — displays quota cards (50 pages remaining).
- [ ] Visit `/convert` — drag and drop a sample bank statement PDF (e.g. SBI or PNB).
- [ ] Bank detection identifies bank name with high confidence (>90%).
- [ ] Table extracts transaction rows (Date, Narration, Withdrawal/Deposit, Balance).
- [ ] Balance validation shows **BALANCED (100% confidence)**.
- [ ] User can customize Ledger names (e.g. change party ledger).
- [ ] Click **Download Tally XML** — browser downloads `.xml` file.
- [ ] Click **Download Excel** — browser downloads 11-column `.xlsx` file.
- [ ] Return to `/dashboard` — pages used updates correctly based on statement length.

### E. Admin Command Center
- [ ] Visit `/admin` without logging in — automatically redirected to `/admin/login`.
- [ ] Log in with regular user credentials at `/admin/login` — rejected with HTTP 403 Forbidden.
- [ ] Log in with `admin@tallyxml.in` — redirected to `/admin`.
- [ ] Admin overview displays total users, total conversions, and system status.
- [ ] Visit `/admin/convert` — Admin Converter allows manual bank parser override.
- [ ] Admin conversions bypass the daily 50-page quota.
- [ ] Visit `/admin/users` — registered users are visible with role status.
- [ ] Visit `/admin/parsers` — all 38 bank parsers are listed with signatures.
- [ ] Visit `/admin/settings` — allows toggling maintenance mode or site mode.

---

## 18. STEP 12: Remove Local Development URLs (No Localhost in Production)

Before opening the site to real users, verify that no hardcoded development addresses remain in your production build.

### 1. Audit Script to Run in Repository

Run this search command from your project root:

```bash
cd "d:\KANGRA HUB FREE TALLY XML"

# Search for localhost:8000 across frontend source code:
git grep "localhost:8000" frontend/src/
```

**Expected results:**
The only occurrence in `frontend/src/` is in `frontend/src/lib/api.ts`:
```typescript
const API_BASE = typeof window !== 'undefined'
  ? (process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/api')
  : 'http://127.0.0.1:8000/api';
```
This is a safe development fallback. In production on Netlify, `process.env.NEXT_PUBLIC_API_URL` is provided by Netlify, so the browser **never** calls `localhost:8000`.

### 2. Verify Render URL in Deployed JavaScript

To be 100% certain:
1. Open your live Netlify site in Chrome/Firefox.
2. Press `F12` to open DevTools -> click **Sources** tab.
3. Press `Ctrl + Shift + F` (Search all files).
4. Search for: `onrender.com`.
5. You should see your live Render API backend URL embedded inside the compiled chunk, confirming that production is pointed to your cloud backend.

---

## 19. STEP 13: Optional Custom Domain Setup & DNS

If you own a custom domain (such as `tallyxml.in` or `tally.kangrahub.com`):

### 1. Add Domain in Netlify

1. In the Netlify Dashboard, go to your site.
2. Click **Site configuration** -> **Domain management**.
3. Click **Add a domain**.
4. Enter your custom domain (e.g. `tallyxml.in`).
5. Netlify will prompt you to configure DNS records.

### 2. Configure DNS Records at Your Registrar (GoDaddy / Namecheap / Cloudflare)

Add either an `A` record or `CNAME` record:

| Type | Name / Host | Target / Value | TTL |
|---|---|---|---|
| **CNAME** | `tally` (for subdomain `tally.domain.com`) | `YOUR_NETLIFY_SITE.netlify.app` | Automatic / 3600 |
| **A** | `@` (for root domain `domain.com`) | `75.2.60.5` (Netlify load balancer) | Automatic / 3600 |
| **CNAME** | `www` | `YOUR_NETLIFY_SITE.netlify.app` | Automatic / 3600 |

### 3. Netlify Automatic HTTPS (SSL)

Once DNS propagates (usually 5 to 30 minutes), scroll to **HTTPS** in Netlify Domain management and click **Verify DNS configuration**. Netlify will automatically issue a free Let's Encrypt SSL certificate.

### 4. Update Other Services with Your Custom Domain

> [!IMPORTANT]
> Once your custom domain is active, update the following three locations:
> 
> 1. **Supabase Dashboard -> Authentication -> URL Configuration**:
>    - Set **Site URL** to `https://tallyxml.in`
>    - Add `https://tallyxml.in/**` to **Redirect URLs**
> 
> 2. **Render Dashboard -> Environment Variables**:
>    - Update `FRONTEND_URL` to `https://tallyxml.in`
>    - Update `CORS_ORIGINS` to `https://tallyxml.in,https://YOUR_NETLIFY_SITE.netlify.app,http://localhost:3000`
> 
> 3. **Netlify Dashboard -> Environment Variables**:
>    - Update `NEXT_PUBLIC_SITE_URL` to `https://tallyxml.in`
>    - Trigger a redeploy (**Deploys** -> **Trigger deploy** -> **Deploy site**) so Next.js embeds the updated metadata URL.

---

## 20. Render Free-Tier Limitations & Keep-Alive Strategy

### The 15-Minute Inactivity Spindown

On Render's Free Plan:
- After **15 minutes with no incoming HTTP requests**, Render puts your Web Service into sleep mode.
- When the next user visits your site and uploads a statement, Render spins up the container.
- This **cold start takes 50 to 70 seconds**. During this time, the user might see a loading spinner.

### Free Keep-Alive Solution (Zero Cost)

You can prevent cold starts completely by setting up a free automated uptime ping:

1. Sign up for a free account at [UptimeRobot.com](https://uptimerobot.com) or [Cron-Job.org](https://cron-job.org).
2. Click **Add New Monitor**.
3. Configure the monitor:
   - **Monitor Type**: `HTTP(s)`
   - **Friendly Name**: `Kangra Hub Backend Ping`
   - **URL**: `https://YOUR_RENDER_SERVICE.onrender.com/health`
   - **Monitoring Interval**: Every **10 minutes**
4. Save the monitor.

**Why this works:**  
The `/health` endpoint is extremely lightweight (takes ~5 ms, executes 0 database queries, and uses negligible memory). Pinging it every 10 minutes keeps the Render service warm 24/7 without exhausting free compute limits.

---

## 21. File Storage Architecture & Ephemeral Disk Warning

### How PDF, Excel, and XML Files Are Handled

> [!WARNING]
> **Render's Local File System is Ephemeral!**  
> Any file written to the local disk on Render will be deleted whenever the container sleeps, restarts, or deploys a new commit.

Kangra Hub Free Tally XML is specifically engineered to be immune to this limitation:

1. **Uploads & Parsing**:
   - When a user uploads a PDF, it is saved into a designated temporary directory:  
     `tempfile.gettempdir()/kangra_hub_tally` (`/tmp/kangra_hub_tally` on Linux).
   - The extraction engine uses Python's `temporary_upload_file` context manager, which **automatically deletes the PDF immediately in a `finally:` block** as soon as transaction extraction completes.
2. **Database Persistence**:
   - The extracted transactions, balance validation results, and metadata snapshot are serialized and saved directly to Supabase (`public.conversion_jobs`). This database data is **permanent** and never lost.
3. **XML and Excel Downloads**:
   - Tally XML and 11-column Excel files are generated on-the-fly from the stored database snapshot and streamed directly to the user's browser response.
4. **Automated Scratch File Purge**:
   - The backend includes a lifespan startup task `cleanup_old_temp_files(max_age_minutes=60)` that scrubs any abandoned scratch files on boot.

---

## 22. Continuous Deployment (Automatic Git Deploys)

Both Netlify and Render are configured for continuous deployment:

```text
Edit code on your local computer
              │
              ▼
git add .
git commit -m "Update bank parser signature"
git push origin main
              │
              ├──────────────────────────────────┐
              ▼                                  ▼
     GitHub notifies Netlify           GitHub notifies Render
              │                                  │
     Netlify pulls `frontend/`          Render pulls `backend/`
     Runs `npm run build`               Runs `pip install`
     Deploys new frontend CDN           Restarts Uvicorn container
```

### How to Manually Trigger a Redeployment

If you change an environment variable and need to rebuild immediately without pushing code:

- **On Netlify**: Go to **Deploys** -> click **Trigger deploy** -> select **Deploy site**.
- **On Render**: Go to your web service -> click **Manual Deploy** -> select **Deploy latest commit** (or **Clear build cache & deploy**).

---

## 23. Rollback & Disaster Recovery

If an unexpected bug breaks production after a code push, you can revert to a previous working state in under 60 seconds:

### Instant Rollback on Netlify (Frontend)
1. Go to your site dashboard on [Netlify](https://app.netlify.com).
2. Click the **Deploys** tab.
3. You will see a list of all historical builds with timestamps.
4. Click on the last known working deploy.
5. Click **Publish deploy**. Netlify instantly points global edge routing to that previous build.

### Rollback on Render (Backend)
1. Go to your service dashboard on [Render](https://dashboard.render.com).
2. Click **Events** or **Deploys** in the left menu.
3. Find the previous successful build.
4. Click the three dots (`...`) next to that build and select **Rollback to this deploy**.

### Git Level Rollback
To permanently revert code in GitHub:
```bash
git log -n 5 --oneline
# Revert the most recent commit:
git revert HEAD --no-edit
git push origin main
```

---

## 24. Production Security Checklist

Verify these 14 security rules before public launch:

- [ ] **No Secret Keys in Frontend**: `SUPABASE_SERVICE_ROLE_KEY` is **NOT** present in `frontend/.env.local`, Netlify environment variables, or client JavaScript.
- [ ] **`.gitignore` Enforced**: Check that `.env` and `*.env.*` are excluded from Git.
- [ ] **Row Level Security (RLS) Active**: RLS is enabled on all 13 Supabase tables.
- [ ] **Role Verification Server-Side**: Privileged endpoints (`/api/admin/*`) strictly verify JWT claims and database role, rejecting unauthorized users with HTTP 403.
- [ ] **Strict Password Requirement**: Minimum 8 characters for administrator accounts.
- [ ] **File Size Limit**: PDF uploads larger than 25 MB are rejected by FastAPI before reading into memory.
- [ ] **Ephemeral File Cleanup**: Uploaded PDFs are wiped immediately after parsing.
- [ ] **CORS Restricted**: Allowed origins specify your exact Netlify domain and custom domain.
- [ ] **HTTPS Enforced**: Both Netlify and Render enforce TLS/HTTPS on all routes.
- [ ] **Rate Limiting**: Daily limit of 50 pages enforced server-side with PostgreSQL atomic row locks (`SELECT ... FOR UPDATE`).
- [ ] **No Hardcoded Passwords**: All admin and user accounts are authenticated through Supabase GoTrue Auth.
- [ ] **XML Entity Escaping**: Special characters (`&`, `<`, `>`, `"`, `'`) in party narrations are escaped to prevent Tally XML injection.
- [ ] **Zero Discrepancy Gate**: XML generation is blocked with HTTP 400 if statement mathematical balance discrepancy != ₹0.00.
- [ ] **Section 129 Payment Isolation**: Manual UPI QR code is accessible only in the authenticated Admin Console, never exposed to unauthorized visitors.

---

## 25. Comprehensive Troubleshooting Guide

### 1. Netlify Build Fails (`npm run build`)
* **Symptom**: Netlify deployment log ends with `Error: Command "npm run build" exited with code 1`.
* **Fixes**:
  1. Check **Base directory**: Ensure Base directory is set to `frontend` (not root).
  2. Check **Node version**: In Netlify environment variables, add `NODE_VERSION=20.10.0`.
  3. Run `npm run build` locally in `frontend/` to view exact TypeScript errors before deploying.

### 2. Render Build Fails (`pip install` error)
* **Symptom**: Render build log shows `error: Microsoft Visual C++ 14.0 or greater is required` or dependency resolution error.
* **Fixes**:
  1. Check **Build Command**: Ensure it is set to:  
     `pip install --upgrade pip && pip install -r requirements.txt`
  2. Check **Root Directory**: Ensure Root Directory on Render is set to `backend`.
  3. Check **Runtime**: Ensure runtime is `Python 3` (Python 3.11 or 3.12).

### 3. HTTP 401 Unauthorized
* **Symptom**: Browser DevTools shows `401 Unauthorized` on API calls.
* **Fixes**:
  1. Check if token expired: Log out and log back in to get a fresh token.
  2. Verify `SUPABASE_URL` and `SUPABASE_ANON_KEY` match between Supabase Dashboard, Netlify, and Render.
  3. Ensure the browser request includes `Authorization: Bearer <JWT_TOKEN>`.

### 4. HTTP 403 Forbidden on `/admin`
* **Symptom**: Logging in as admin displays "403 Forbidden - Administrator Access Required".
* **Fixes**:
  1. Check if admin promotion SQL was executed: In Supabase SQL Editor, run:
     ```sql
     SELECT public.promote_user_to_admin('admin@tallyxml.in');
     ```
  2. Confirm `public.profiles.role` equals `'ADMIN'` for your user ID.
  3. Log out and log back in to refresh JWT claims in your browser.

### 5. CORS Errors (`Access-Control-Allow-Origin`)
* **Symptom**: Browser console logs: `Cross-Origin Request Blocked: The Same Origin Policy disallows reading the remote resource`.
* **Fixes**:
  1. In Render environment variables, verify `CORS_ORIGINS` contains your exact Netlify frontend domain without trailing slashes:
     `https://YOUR_NETLIFY_SITE.netlify.app`
  2. If using a custom domain, ensure it is added to `CORS_ORIGINS`:
     `https://YOUR_CUSTOM_DOMAIN,https://YOUR_NETLIFY_SITE.netlify.app,http://localhost:3000`
  3. Trigger a manual redeployment on Render after modifying CORS variables.

### 6. Backend Unavailable / Request Timeout (504 Gateway Timeout)
* **Symptom**: PDF upload hangs for ~60 seconds and returns 504.
* **Fixes**:
  1. This is typically a Render Free Tier cold start. Wait 60 seconds and try uploading again.
  2. Configure an uptime ping to `/health` as documented in Section 20 to keep the service warm.
  3. If statement is over 50 pages, ensure PDF is split or user is an admin with higher timeout allowances.

### 7. Supabase Database Connection Error
* **Symptom**: Backend logs show `supabase.lib.client_exceptions.SupabaseException` or failed connection.
* **Fixes**:
  1. In Render environment variables, ensure `SUPABASE_URL` has no trailing slash (e.g. `https://YOUR_SUPABASE_PROJECT_REF.supabase.co`).
  2. Ensure `SUPABASE_SERVICE_ROLE_KEY` is the secret key from Supabase Dashboard -> Settings -> API -> `service_role` (or Secret Key).

### 8. Password Reset Email Not Arriving
* **Symptom**: User clicks "Send Reset Link" but no email is received.
* **Fixes**:
  1. Check email Spam/Junk folder.
  2. Supabase Free Tier has a default rate limit of 3 emails per hour for standard SMTP. For production volume, connect custom SMTP (Resend, SendGrid, or AWS SES) in Supabase Dashboard -> Authentication -> Email -> SMTP Settings.
  3. Ensure `https://YOUR_NETLIFY_SITE.netlify.app/admin/reset-password` is added under Supabase Auth **Redirect URLs**.

### 9. PDF Upload Fails (`File Too Large`)
* **Symptom**: User receives HTTP 413 or "File exceeds maximum upload size".
* **Fixes**:
  1. Verify the PDF is under 25 MB.
  2. If higher file sizes are required, increase `MAX_UPLOAD_SIZE_MB` in Render environment variables.

### 10. XML Download Fails with Validation Discrepancy
* **Symptom**: Backend returns `HTTP 400 - Mathematical discrepancy in running balance`.
* **Fixes**:
  1. This is an intentional financial safety guardrail. Kangra Hub guarantees zero silent accounting loss.
  2. If the bank statement has missing pages or unread opening rows, inspect the suspect row highlighted in amber in the UI.
  3. Use `/admin/convert` if you need to manually select a different bank parser for ambiguous bank statement layouts.

---

## 26. Deployment Security Audit & Architectural Notes

### Repository Security Audit Result
- An automated cryptographic and pattern scan was executed across all 236 tracked files in the Git repository.
- **Verdict: CLEAN.** Zero real Supabase secret keys, zero service-role keys, zero SMTP passwords, and zero private tokens are stored in the tracked repository code.
- All `.env` and `.env.local` files are confirmed excluded by `.gitignore`.

### Architectural Notes
1. **Native Python vs Docker**:
   - A `backend/Dockerfile` exists, but Render's native **Python 3** web service runtime is faster, simpler to maintain, and requires no Docker cache management. The native runtime is recommended.
2. **System Libraries for PDF Processing**:
   - The PDF engine relies exclusively on `pdfplumber` and `pypdf`. Both install pure Python and pre-compiled wheels via `pip install -r requirements.txt`. **No external Linux packages (such as Poppler or Tesseract OCR) are required.**
3. **CORS Implementation**:
   - `backend/main.py` utilizes FastAPI's `CORSMiddleware`. Render's environment should set `FRONTEND_URL` and `CORS_ORIGINS` to your production Netlify domain for strict origin isolation.
4. **Unit Test Finding**:
   - In `backend/app/api/admin.py` line 1158, `test_admin_grant_unlimited_flow` imports `db` from `app.core.db`. The application startup and all primary conversion, auth, and parser routes run independently of this legacy helper. All production database operations run directly via `SupabaseService`.

---

## 27. Final Deployment Checklist

Print or review this checklist before declaring production live:

```text
PRE-FLIGHT & REPOSITORY:
[ ] Local frontend build passes with 0 errors (npm run build)
[ ] Local backend starts and /health returns healthy
[ ] .env and .env.local files are verified excluded by .gitignore
[ ] Code pushed to GitHub origin/main without any hardcoded credentials

SUPABASE CONFIGURATION:
[ ] Supabase project created in South Asia (Mumbai) - ap-south-1
[ ] database/supabase_complete.sql executed successfully in SQL Editor
[ ] All 13 tables verified with RLS enabled
[ ] 38 Indian bank parsers verified seeded in public.bank_parsers
[ ] check_and_record_usage stored procedure verified active
[ ] Supabase Site URL set to Netlify production domain
[ ] Supabase Redirect URLs contain both production and localhost callback paths

RENDER BACKEND DEPLOYMENT:
[ ] Web Service created with Root Directory set to backend
[ ] Python 3 runtime selected with pip install build command
[ ] Start command configured: uvicorn main:app --host 0.0.0.0 --port $PORT --workers 1
[ ] Backend environment variables entered directly into Render Environment tab
[ ] SUPABASE_SERVICE_ROLE_KEY (Secret Key) stored ONLY in Render
[ ] Service deployed and https://YOUR_RENDER_SERVICE.onrender.com/health returns HTTP 200
[ ] Optional UptimeRobot monitor configured for 10-minute /health keep-alive ping

NETLIFY FRONTEND DEPLOYMENT:
[ ] Project created with Base directory set to frontend
[ ] Build command configured as npm run build
[ ] NEXT_PUBLIC_API_URL set to https://YOUR_RENDER_SERVICE.onrender.com/api (with /api)
[ ] NEXT_PUBLIC_SUPABASE_URL and NEXT_PUBLIC_SUPABASE_ANON_KEY (Publishable Key) configured
[ ] Netlify build completes with all 44 routes generated
[ ] Deployed site loads with clean typography and logo.webp rendered

AUTHENTICATION & ADMINISTRATION:
[ ] Admin user admin@tallyxml.in registered through live /signup
[ ] SELECT public.promote_user_to_admin('admin@tallyxml.in') executed in Supabase
[ ] Admin logs in at /admin/login and accesses /admin with UNLIMITED badge
[ ] Standard test user registers and logs in at /login
[ ] Unauthenticated access to /admin properly redirects to /admin/login
[ ] Standard user attempting /admin access receives 403 Forbidden

FUNCTIONAL CONVERSION VERIFICATION:
[ ] Test bank statement PDF uploaded to /convert
[ ] Bank detection identifies bank name with >90% confidence
[ ] Transactions extract cleanly with payee narrations
[ ] Mathematical balance verifies with 100% confidence
[ ] Downloaded Tally XML conforms to SAMPLE.xml double-entry format
[ ] Downloaded Excel matches the 11 standard Tally columns
[ ] Daily quota counter decrements accurately in /dashboard

SECURITY & TEARDOWN:
[ ] Browser DevTools confirms no localhost:8000 calls in production
[ ] No private service role keys exposed in client JavaScript bundle
[ ] Zero silent financial data loss guaranteed
```

---

*Kangra Hub Free Tally XML is ready for production use.*
