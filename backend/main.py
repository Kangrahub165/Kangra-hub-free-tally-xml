import uuid
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, status
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

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global Exception Handlers
@app.exception_handler(AppBaseException)
async def handle_app_exception(request: Request, exc: AppBaseException):
    app_logger.warning(f"Handled error [{exc.internal_code}] (Ref: {exc.reference_id}): {exc.user_message}")
    return JSONResponse(
        status_code=exc.status_code,
        content=exc.detail
    )

@app.exception_handler(Exception)
async def handle_unexpected_exception(request: Request, exc: Exception):
    ref_id = f"KH-{uuid.uuid4().hex[:6].upper()}"
    app_logger.error(f"Unhandled exception (Ref: {ref_id}): {str(exc)}", exc_info=True)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "error": True,
            "message": "Something went wrong while processing your statement. Please try again or contact support.",
            "code": "ERR_INTERNAL_SERVER_ERROR",
            "reference_id": ref_id
        }
    )

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

    return {
        "status": "healthy",
        "app": settings.app_name,
        "site_mode": settings.site_mode,
        "app_env": getattr(settings, "app_env", "production"),
        "supabase_connected": SupabaseService.is_configured(),
        "smtp_configured": smtp_service.is_configured(),
        "timestamp": datetime.now(timezone.utc).isoformat()
    }

