import os
import uuid
from typing import Optional
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, Response, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.core.config import settings
from app.core.exceptions import AppBaseException
from app.utils.logger import app_logger
from app.utils.temp_files import cleanup_old_temp_files

from app.api.system import router as system_router
from app.api.banks import router as banks_router
from app.api.usage import router as usage_router
from app.api.conversions import router as conversions_router
from app.api.admin import router as admin_router
from app.api.ledgers import router as ledgers_router
from app.api.auth import router as auth_router
from app.api.appeals import router as appeals_router
from app.api.payments import router as payments_router
from app.api.quota import router as quota_router

@asynccontextmanager
async def lifespan(app: FastAPI):
    app_logger.info("Starting Kangra Hub Free Tally XML Engine...")
    
    # Verify environment loading at startup
    if settings.supabase_url:
        masked_url = settings.supabase_url[:30] + "..." if len(settings.supabase_url) > 30 else settings.supabase_url
        has_anon = bool(settings.supabase_anon_key)
        has_service = bool(settings.supabase_service_role_key)
        app_logger.info(f"Supabase Auth Environment: LOADED ({masked_url}, anon_key: {has_anon}, service_key: {has_service})")
    else:
        app_logger.warning("Supabase Auth Environment: NOT CONFIGURED (SUPABASE_URL is empty in backend/.env). Admin login will return HTTP 503 until credentials are added.")

    cleaned = cleanup_old_temp_files()
    if cleaned > 0:
        app_logger.info(f"Cleaned up {cleaned} legacy temporary files.")
    yield
    app_logger.info("Shutting down Kangra Hub Free Tally XML Engine...")

app = FastAPI(
    title=settings.app_name,
    description="Bank Statement PDF to Tally XML Conversion Platform",
    version="1.0.0",
    lifespan=lifespan
)

# Dynamic CORS Configuration from Environment & Settings (PRD Item 1 & Deployment Hardening)
origins_set = {
    "https://kangrahubtallyxml.netlify.app",
    "https://deploy-preview-1--kangrahubtallyxml.netlify.app",
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "http://localhost:8000",
    "http://127.0.0.1:8000",
}

# Collect all potential origin sources: CORS_ORIGINS, ALLOWED_ORIGINS, FRONTEND_URL, settings
origin_sources = [
    os.getenv("CORS_ORIGINS", ""),
    os.getenv("ALLOWED_ORIGINS", ""),
    os.getenv("FRONTEND_URL", ""),
    getattr(settings, "cors_origins", ""),
    getattr(settings, "allowed_origins", ""),
    getattr(settings, "frontend_url", ""),
]
for src in origin_sources:
    if src:
        for raw_origin in str(src).split(","):
            clean_orig = raw_origin.strip().rstrip("/")
            if clean_orig:
                origins_set.add(clean_orig)

allowed_origins = sorted(list(origins_set))
app_logger.info(f"CORS Allowed Origins: {allowed_origins}")

def get_cors_origin_for_request(request: Request) -> Optional[str]:
    origin = request.headers.get("origin")
    if not origin:
        return None
    origin_clean = origin.strip().rstrip("/")
    if origin in origins_set or origin_clean in origins_set:
        return origin
    if "netlify.app" in origin or "localhost" in origin or "127.0.0.1" in origin:
        return origin
    return None

def apply_cors_headers(response: Response, request: Request) -> Response:
    origin = get_cors_origin_for_request(request)
    if origin:
        response.headers["Access-Control-Allow-Origin"] = origin
        response.headers["Access-Control-Allow-Credentials"] = "true"
        response.headers["Access-Control-Allow-Methods"] = "GET, POST, PUT, DELETE, OPTIONS, PATCH, HEAD"
        req_headers = request.headers.get(
            "access-control-request-headers",
            "Authorization, Content-Type, Accept, Origin, X-Requested-With, X-Total-Count"
        )
        response.headers["Access-Control-Allow-Headers"] = req_headers
        response.headers["Access-Control-Expose-Headers"] = "Content-Disposition, Content-Type, Content-Length, X-Total-Count"
        response.headers["Access-Control-Max-Age"] = "86400"
    return response

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_origin_regex=r"^https?://(localhost|127\.0\.0\.1|.*\.netlify\.app)(:\d+)?$",
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS", "PATCH", "HEAD"],
    allow_headers=["*"],
    expose_headers=["Content-Disposition", "Content-Type", "Content-Length", "X-Total-Count"],
)

@app.middleware("http")
async def ensure_cors_headers(request: Request, call_next):
    """Guarantees CORS headers are attached on all responses, including OPTIONS preflights and uncaught exceptions."""
    if request.method == "OPTIONS":
        resp = Response(status_code=200)
        return apply_cors_headers(resp, request)

    try:
        response = await call_next(request)
    except Exception as exc:
        ref_id = f"KH-{uuid.uuid4().hex[:6].upper()}"
        app_logger.error(f"Middleware caught unhandled exception (Ref: {ref_id}): {exc}", exc_info=True)
        response = JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "error": True,
                "message": "Something went wrong while processing your statement. Please try again or contact support.",
                "code": "ERR_INTERNAL_SERVER_ERROR",
                "reference_id": ref_id
            }
        )
    return apply_cors_headers(response, request)

# Global Exception Handlers
@app.exception_handler(HTTPException)
async def handle_http_exception(request: Request, exc: HTTPException):
    if isinstance(exc.detail, dict):
        content = dict(exc.detail)
        content["detail"] = exc.detail
    else:
        content = {"detail": exc.detail, "message": str(exc.detail)}
    resp = JSONResponse(status_code=exc.status_code, content=content)
    return apply_cors_headers(resp, request)

@app.exception_handler(AppBaseException)
async def handle_app_exception(request: Request, exc: AppBaseException):
    app_logger.warning(f"Handled error [{exc.internal_code}] (Ref: {exc.reference_id}): {exc.user_message}")
    resp = JSONResponse(
        status_code=exc.status_code,
        content=exc.detail
    )
    return apply_cors_headers(resp, request)

@app.exception_handler(Exception)
async def handle_unexpected_exception(request: Request, exc: Exception):
    ref_id = f"KH-{uuid.uuid4().hex[:6].upper()}"
    app_logger.error(f"Unhandled exception (Ref: {ref_id}): {str(exc)}", exc_info=True)
    resp = JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "error": True,
            "message": "Something went wrong while processing your statement. Please try again or contact support.",
            "code": "ERR_INTERNAL_SERVER_ERROR",
            "reference_id": ref_id
        }
    )
    return apply_cors_headers(resp, request)

# Register API routers
app.include_router(system_router, prefix=settings.api_prefix)
app.include_router(banks_router, prefix=settings.api_prefix)
app.include_router(usage_router, prefix=settings.api_prefix)
app.include_router(conversions_router, prefix=settings.api_prefix)
app.include_router(admin_router, prefix=settings.api_prefix)
app.include_router(ledgers_router, prefix=settings.api_prefix)
app.include_router(auth_router, prefix=settings.api_prefix)
app.include_router(appeals_router, prefix=f"{settings.api_prefix}/appeals")
app.include_router(payments_router)
app.include_router(quota_router, prefix=settings.api_prefix)

@app.get("/")
async def root():
    return {
        "status": "online",
        "app": settings.app_name,
        "site_mode": settings.site_mode,
        "swagger_docs": "/docs",
        "health_check": "/health",
        "frontend_ui": "http://localhost:3000"
    }

@app.get("/health")
@app.get("/api/health")
async def health_check():
    from app.core.supabase_service import SupabaseService
    from app.core.smtp_service import smtp_service
    from datetime import datetime, timezone

    is_sb_configured = SupabaseService.is_configured()
    sb_url = SupabaseService.get_url()
    sb_key = SupabaseService.get_api_key()

    return {
        "status": "healthy",
        "app": settings.app_name,
        "site_mode": settings.site_mode,
        "app_env": getattr(settings, "app_env", "production"),
        "supabase_connected": is_sb_configured,
        "supabase_url_configured": bool(sb_url),
        "supabase_key_configured": bool(sb_key),
        "smtp_configured": smtp_service.is_configured(),
        "timestamp": datetime.now(timezone.utc).isoformat()
    }

