import os
from pathlib import Path
from typing import Optional
from dotenv import load_dotenv
from pydantic_settings import BaseSettings

# Locate backend/.env and root .env dynamically regardless of execution CWD
BACKEND_DIR = Path(__file__).resolve().parent.parent.parent
ENV_FILE_BACKEND = BACKEND_DIR / ".env"
ENV_FILE_ROOT = BACKEND_DIR.parent / ".env"

if ENV_FILE_ROOT.exists():
    load_dotenv(str(ENV_FILE_ROOT), override=False)
if ENV_FILE_BACKEND.exists():
    load_dotenv(str(ENV_FILE_BACKEND), override=True)

class Settings(BaseSettings):
    app_name: str = "Kangra Hub Free Tally XML"
    app_env: str = "development"
    api_prefix: str = "/api"
    
    # Supabase credentials
    supabase_url: str = ""
    supabase_anon_key: str = ""
    supabase_service_role_key: str = ""
    frontend_url: str = "http://localhost:3000"
    admin_email: str = "admin@tallyxml.in"
    admin_recovery_email: str = "kangrahub@gmail.com"
    
    # SMS / OTP credentials (Optional: Fast2SMS, Twilio, etc.)
    fast2sms_api_key: str = ""
    twilio_account_sid: str = ""
    twilio_auth_token: str = ""
    twilio_from_number: str = ""
    otp_expiry_minutes: int = 10
    otp_cooldown_seconds: int = 60

    # Production-Ready SMTP Email configuration
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    smtp_from_email: str = ""
    smtp_from_name: str = "Kangra Hub Free Tally XML"
    smtp_use_tls: bool = True
    smtp_use_ssl: bool = False
    
    # System settings defaults
    site_mode: str = "FREE"  # "FREE" or "PAID"
    free_daily_page_limit: int = 50
    max_upload_size_mb: int = 25
    max_pages_per_file: int = 2500
    maintenance_mode: bool = False
    allow_new_signups: bool = True
    default_timezone: str = "Asia/Kolkata"
    
    # Page pricing and payment configurations (PRD: ₹2/page manual UPI)
    page_price_inr: float = 2.0
    payment_upi_id: str = "9418250639@ybl"
    payment_whatsapp_number: str = "+919805987622"
    payment_qr_path: str = "/buy-a-coffee/googlepay_qr.png"

    # Buy a coffee configuration (Admin only)
    buy_coffee_enabled: bool = True
    buy_coffee_upi_id: str = "9418250639@ybl"
    buy_coffee_payment_url: str = ""
    buy_coffee_button_text: str = "Buy Me a Coffee ☕"
    buy_coffee_message: str = "Enjoying Kangra Hub Free Tally XML? Support the project with a cup of coffee."
    buy_coffee_qr_path: str = "/buy-a-coffee/googlepay_qr.png"

    # Temp file retention (minutes)
    file_retention_minutes: int = 60

    class Config:
        env_file = str(ENV_FILE_BACKEND)
        extra = "ignore"

settings = Settings()
