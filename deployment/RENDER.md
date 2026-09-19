# Render Deployment Guide & Free Tier Evaluation
**Kangra Hub Free Tally XML — FastAPI Backend Production Deployment**

This document provides complete instructions for deploying the FastAPI backend to [Render](https://render.com), along with an honest technical evaluation of Render Free Tier capabilities and limitations.

---

## 1. Quick Deployment Configuration

- **Service Type**: Web Service (Native Python 3 or Docker)
- **Root Directory**: `backend`
- **Environment**: `Python 3` (3.11 or 3.12)
- **Build Command**: `pip install -r requirements.txt`
- **Start Command**: `uvicorn main:app --host 0.0.0.0 --port $PORT --workers 2`
- **Health Check Path**: `/health`

---

## 2. Step-by-Step Deployment on Render

### Step 1: Create a Web Service
1. Log in to your [Render Dashboard](https://dashboard.render.com).
2. Click **New +** -> **Web Service**.
3. Connect your Git repository (`KANGRA HUB FREE TALLY XML`).
4. Set the **Root Directory** to `backend`.

### Step 2: Configure Runtime Settings
- **Name**: `kangra-hub-backend` (or your choice)
- **Region**: Singapore (`singapore`) or Frankfurt (choose the closest to Mumbai/India for lowest latency)
- **Branch**: `main`
- **Runtime**: `Python 3`
- **Build Command**:
  ```bash
  pip install --upgrade pip && pip install -r requirements.txt
  ```
- **Start Command**:
  ```bash
  uvicorn main:app --host 0.0.0.0 --port $PORT --workers 2
  ```

### Step 3: Configure Environment Variables
Navigate to the **Environment** tab and add the following variables:

| Variable | Recommended / Default Value | Purpose |
|---|---|---|
| `PYTHON_VERSION` | `3.11.8` | Ensures consistent C-extension compatibility |
| `SUPABASE_URL` | `https://your-project.supabase.co` | Supabase API connection URL |
| `SUPABASE_KEY` | `eyJhbGciOi...` | Supabase Anon Key |
| `SUPABASE_SERVICE_ROLE_KEY` | `eyJhbGciOi...` | Supabase Service Role Key (Backend DB access) |
| `CORS_ORIGINS` | `https://kangrahub.com,https://your-site.netlify.app,http://localhost:3000` | Allowed frontend origins (comma-separated) |
| `MAX_FILE_SIZE_MB` | `25` | Maximum allowed bank statement PDF upload size |
| `STATEMENT_TIMEOUT_SECONDS` | `90` | Hard processing timeout for PDF analysis |
| `ENVIRONMENT` | `production` | Deployment mode flag |
| `LOG_LEVEL` | `INFO` | Standard logging verbosity |

---

## 3. Honest Technical Evaluation of Render Free Tier

While Render provides a generous free tier for prototyping, bank statement parsing involves CPU-intensive PDF parsing, font matrix extraction, and geometric table reconstruction. Here is an honest assessment of its limitations:

### 1. Cold Starts (~50 to 70 Seconds)
- **The Issue**: Free web services spin down automatically after **15 minutes of inactivity**. The next incoming HTTP request triggers a cold container boot.
- **Impact**: A user uploading a PDF may experience a 50-70 second loading spinner before the backend even accepts the payload.
- **Mitigation**: 
  - Configure an external uptime monitor (e.g. [UptimeRobot](https://uptimerobot.com) or [Cron-Job.org](https://cron-job.org)) to hit the lightweight `GET /health` endpoint every 10 minutes to prevent container spindown.
  - Frontend display of a friendly *"Server warming up..."* indicator when initial API ping takes longer than 3 seconds.

### 2. Strict 512 MB RAM Ceiling & Out-Of-Memory (OOM) Risks
- **The Issue**: Render Free Tier allocates exactly **512 MB of RAM**.
- **Impact**: Libraries like `pdfplumber` and `pypdf` construct internal geometric bounding boxes, character dictionaries, and stream caches for every PDF page.
  - An 8-page digital PDF (like our verified SBI statement) consumes ~120 MB RAM during parsing — perfectly safe.
  - A dense 40-page corporate bank statement can spike memory usage to 350-450 MB.
  - Two concurrent uploads running simultaneously will exceed 512 MB, causing Linux to immediately kill the process with `SIGKILL 137 (OOMKilled)`.
- **Mitigation**:
  - Run with `--workers 1` or `--workers 2` maximum on Free Tier.
  - Perform immediate explicit garbage collection (`import gc; gc.collect()`) after parsing completes.
  - Stream large files to disk rather than reading the entire binary into memory (`BytesIO`).

### 3. 100-Second Hard HTTP Timeout
- **The Issue**: Render places a hard 100-second timeout on HTTP connections through their reverse proxy.
- **Impact**: On shared 0.1 vCPU free tier cores, extracting 50+ pages of dense tabular data may occasionally approach 70-90 seconds. If it exceeds 100 seconds, Render terminates the request with `504 Gateway Timeout`.
- **Mitigation**:
  - Standard user conversions are capped at 50 pages per statement, keeping extraction times under 15-20 seconds.
  - Background async processing or queueing is recommended for files above 50 pages.

### 4. Ephemeral Local Disk
- **The Issue**: Free tier local disk is non-persistent and deleted whenever the container restarts or re-deploys.
- **Impact**: Uploaded temporary files and generated Tally XML files saved to local disk will not survive instance restarts.
- **Mitigation**:
  - The application generates Tally XML in-memory and streams it directly to the user response, with optional storage in Supabase Storage (`storage.buckets`).
  - Temporary disk scratch directories are automatically unlinked and cleaned up in a `finally:` block.

---

## 4. Recommended Low-Cost Production Upgrade

For professional, commercial production use:

| Provider | Plan | Monthly Cost | Specifications | Recommendation |
|---|---|---|---|---|
| **Render** | **Starter** | **$7 / month** | 1 vCPU, 1 GB RAM, 0s cold start | **Recommended for easiest setup** |
| **Railway** | Hobby / Pro | ~$5 / month | Pay-per-use, 2 GB RAM, 0s cold start | Excellent developer experience |
| **DigitalOcean** | Basic App | $5 - $10 / month | 1 GB - 2 GB RAM, dedicated uptime | High stability |
| **Hetzner VPS** | CX22 | ~€3.79 / month | 2 vCPU, 4 GB RAM, 40 GB NVMe | Best cost-to-performance ratio |

---

## 5. Health Check & Diagnostic Endpoints

The backend includes dedicated diagnostic endpoints:
- `GET /health`: Fast, zero-DB health check (returns `{"status": "ok"}`).
- `GET /api/v1/system/status`: Comprehensive status including memory usage, uptime, and database connectivity.
