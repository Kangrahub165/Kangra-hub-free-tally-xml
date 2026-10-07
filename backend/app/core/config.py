import os
from pathlib import Path
from typing import Optional
from dotenv import load_dotenv
from pydantic import model_validator
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
    app_name: str = "Kangra Hub — Sales & Purchase"
    app_env: str = "development"
    api_prefix: str = "/api"
    
    # Supabase credentials
    supabase_url: str = ""
    supabase_anon_key: str = ""
    supabase_publishable_key: str = ""
    supabase_service_role_key: str = ""
    supabase_secret_key: str = ""

    @model_validator(mode="after")
    def sync_supabase_keys(self):
        # Sync secret key with service role key for backwards compatibility
        if self.supabase_secret_key and not self.supabase_service_role_key:
            self.supabase_service_role_key = self.supabase_secret_key
        elif self.supabase_service_role_key and not self.supabase_secret_key:
            self.supabase_secret_key = self.supabase_service_role_key

        # Sync publishable key with anon key for backwards compatibility
        if self.supabase_publishable_key and not self.supabase_anon_key:
            self.supabase_anon_key = self.supabase_publishable_key
        elif self.supabase_anon_key and not self.supabase_publishable_key:
            self.supabase_publishable_key = self.supabase_anon_key

        return self
    
    frontend_url: str = "http://localhost:3000"
    admin_email: str = "admin@kangrahub.sales"
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
    smtp_from_name: str = "Kangra Hub — Sales & Purchase"
    smtp_use_tls: bool = True
    smtp_use_ssl: bool = False
    
    # System settings defaults
    site_mode: str = "FREE"  # "FREE" or "PAID"
    free_daily_page_limit: int = 5   # Maintained for backward compatibility
    free_daily_bill_limit: int = 5   # PRD: 5 bills per user per day FREE
    max_upload_size_mb: int = 25
    max_pages_per_file: int = 2500
    maintenance_mode: bool = False
    allow_new_signups: bool = True
    default_timezone: str = "Asia/Kolkata"
    
    # Bill pricing and payment configurations (PRD: ₹10/additional bill)
    page_price_inr: float = 10.0     # Maintained for backward compatibility
    bill_price_inr: float = 10.0     # PRD: ₹10 per additional bill
    payment_upi_id: str = "Kangrahub@pnb"
    payment_whatsapp_number: str = "+919805987622"
    payment_qr_path: str = "/buy-a-coffee/googlepay_qr.png"

    # Buy a coffee configuration (Admin only)
    buy_coffee_enabled: bool = True
    buy_coffee_upi_id: str = "Kangrahub@pnb"
    buy_coffee_payment_url: str = ""
    buy_coffee_button_text: str = "Buy Me a Coffee ☕"
    buy_coffee_message: str = "Enjoying Kangra Hub Free Tally XML? Support the project with a cup of coffee."
    buy_coffee_qr_path: str = "/buy-a-coffee/googlepay_qr.png"

    # Temp file retention (minutes)
    file_retention_minutes: int = 60

    # Razorpay Staff Membership configuration (PRD: Rs 499, Manual Renewal)
    razorpay_key_id: str = ""
    razorpay_key_secret: str = ""
    razorpay_webhook_secret: str = ""
    razorpay_payment_button_id: str = "pl_Tk9nSzYSLpyHvZ"
    staff_membership_price_inr: float = 499.0
    staff_membership_price_paise: int = 49900
    staff_membership_duration_days: int = 30

    # Gemini AI configuration (PRD: Intelligent document understanding layer)
    gemini_api_key: str = ""
    gemini_model: str = "gemini-3.1-flash-lite"
    ai_enabled: bool = True
    ai_max_retries: int = 2
    ai_timeout_seconds: int = 30
    ai_concurrency_limit: int = 2
    ai_daily_request_limit: int = 500

    # PRD Oct 2026: Invoice OCR -> Tally-Ready XML (Sales & Purchase) Engine V2
    enable_prd_invoice_ocr_v2: bool = True

    class Config:
        env_file = str(ENV_FILE_BACKEND)
        extra = "ignore"

settings = Settings()
