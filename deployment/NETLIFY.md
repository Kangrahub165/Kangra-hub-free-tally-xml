# Netlify Deployment Guide (Next.js 14 App Router)
**Kangra Hub Free Tally XML — Frontend Production Deployment**

This guide provides instructions for deploying the Next.js 14 App Router frontend to Netlify.

---

## 1. Project Configuration Summary

- **Framework**: Next.js 14 (App Router)
- **Base Directory**: `frontend`
- **Build Command**: `npm run build`
- **Publish Directory**: `frontend/.next`
- **Node.js Version**: `20.10.0` (LTS)
- **Package Manager**: `npm`

---

## 2. Step-by-Step Deployment via Netlify Dashboard

### Step 1: Connect Git Repository
1. Log in to your [Netlify Dashboard](https://app.netlify.com).
2. Click **Add new site** -> **Import an existing project**.
3. Authorize GitHub / GitLab and select your `KANGRA HUB FREE TALLY XML` repository.

### Step 2: Configure Build Settings
Under **Build settings**, configure the following:
- **Base directory**: `frontend`
- **Build command**: `npm run build`
- **Publish directory**: `.next`
- **Functions directory**: Leave default (managed automatically by `@netlify/plugin-nextjs`)

### Step 3: Configure Environment Variables
Navigate to **Site configuration** -> **Environment variables** and add:

| Key | Example / Recommended Value | Description |
|---|---|---|
| `NEXT_PUBLIC_API_BASE` | `https://api.kangrahub.com` or `https://kangra-hub-backend.onrender.com` | FastAPI backend URL (no trailing slash) |
| `NEXT_PUBLIC_SUPABASE_URL` | `https://your-project.supabase.co` | Supabase API URL |
| `NEXT_PUBLIC_SUPABASE_ANON_KEY` | `eyJhbGciOi...` | Supabase public anonymous key |
| `NEXT_PUBLIC_APP_URL` | `https://kangrahub.com` or your Netlify subdomain | Public URL of the frontend |
| `NODE_VERSION` | `20.10.0` | Node.js runtime version |

### Step 4: Deploy Site
Click **Deploy site**. Netlify will pull the code, install dependencies, compile Next.js pages, and deploy to their edge CDN.

---

## 3. Recommended `netlify.toml` Configuration

For automated, repeatable deployments, add a `netlify.toml` file to the project root:

```toml
[build]
  base = "frontend"
  publish = ".next"
  command = "npm run build"

[build.environment]
  NODE_VERSION = "20.10.0"
  NPM_FLAGS = "--legacy-peer-deps"

[[plugins]]
  package = "@netlify/plugin-nextjs"

# Security & Cache Control Headers
[[headers]]
  for = "/*"
  [headers.values]
    X-Frame-Options = "DENY"
    X-Content-Type-Options = "nosniff"
    Referrer-Policy = "strict-origin-when-cross-origin"
    Permissions-Policy = "camera=(), microphone=(), geolocation=()"
    Content-Security-Policy = "default-src 'self'; script-src 'self' 'unsafe-inline' 'unsafe-eval'; style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; font-src 'self' https://fonts.gstatic.com data:; img-src 'self' data: https: blob:; connect-src 'self' https://*.supabase.co https://*.onrender.com https://api.kangrahub.com;"

# Cache static assets
[[headers]]
  for = "/_next/static/*"
  [headers.values]
    Cache-Control = "public, max-age=31536000, immutable"
```

---

## 4. CORS & Backend Communication Architecture

The Next.js client communicates directly with the FastAPI backend hosted on Render:
```
[Browser Client]
       │
       ├─► (1) Supabase Auth: Obtains Session JWT (`sb-access-token`)
       │
       └─► (2) Direct HTTPS API Calls to FastAPI (`NEXT_PUBLIC_API_BASE`):
               - Headers: `Authorization: Bearer <JWT>`
               - Endpoints:
                 - `/api/conversions/upload`
                 - `/api/conversions/{job_id}/generate`
                 - `/admin/conversions/upload`
                 - `/admin/conversions/{job_id}/override-bank`
```

> [!IMPORTANT]
> Ensure the FastAPI backend `CORS_ORIGINS` environment variable includes your Netlify domain (e.g. `https://kangra-hub.netlify.app` and custom domain `https://kangrahub.com`).

---

## 5. Pre-Deployment Verification Checklist

Before triggering a production build:
- [ ] Run `npm run build` locally in the `frontend` directory and ensure 0 compile errors.
- [ ] Verify all 36 dynamic and static routes compile successfully.
- [ ] Check that no private secrets (e.g. `SUPABASE_SERVICE_ROLE_KEY` or database passwords) are referenced in any `frontend/` files.
- [ ] Confirm `NEXT_PUBLIC_API_BASE` points to your active backend instance.
- [ ] Verify custom 404 and 500 error boundaries exist.

---

## 6. Post-Deployment Smoke Test

1. Visit the deployed Netlify URL.
2. Verify home page loads with clean styling, typography, and interactive components.
3. Test authentication: Sign in / Sign up via Supabase Auth.
4. Navigate to `/convert`: Confirm converter studio renders file dropzone.
5. Log in with an admin account: Confirm `/admin` and `/admin/convert` are accessible, displaying the `ADMIN • UNLIMITED` badge.
