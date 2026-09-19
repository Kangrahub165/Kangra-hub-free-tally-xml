import smtplib
import ssl
import logging
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Tuple, Optional
from app.core.config import settings

logger = logging.getLogger("kangra_hub.smtp")

class SMTPService:
    """
    Production-ready SMTP service for Kangra Hub.
    Handles secure email delivery via TLS/SSL with strict verification email templates.
    Passwords and sensitive connection data are never logged or exposed.
    """

    @staticmethod
    def is_configured() -> bool:
        """Returns True if minimum required SMTP parameters are configured."""
        return bool(
            settings.smtp_host
            and settings.smtp_port
            and (settings.smtp_from_email or settings.smtp_user)
        )

    @classmethod
    def test_connection(cls) -> Tuple[bool, str]:
        """
        Tests connection and authentication to the configured SMTP server.
        Returns: (success: bool, message: str)
        """
        if not cls.is_configured():
            return False, "SMTP server is not configured. Please set SMTP host and sender email in system settings."

        try:
            if settings.smtp_use_ssl or settings.smtp_port == 465:
                context = ssl.create_default_context()
                server = smtplib.SMTP_SSL(settings.smtp_host, settings.smtp_port, context=context, timeout=10)
            else:
                server = smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=10)
                if settings.smtp_use_tls:
                    context = ssl.create_default_context()
                    server.starttls(context=context)

            if settings.smtp_user and settings.smtp_password:
                server.login(settings.smtp_user, settings.smtp_password)

            server.quit()
            return True, f"Successfully connected to SMTP server ({settings.smtp_host}:{settings.smtp_port})"
        except Exception as e:
            logger.error(f"SMTP connection test failed: {str(e)}")
            return False, f"SMTP connection error: {str(e)}"

    @classmethod
    def send_email(
        cls,
        to_email: str,
        subject: str,
        body_text: str,
        html_content: Optional[str] = None
    ) -> Tuple[bool, str]:
        """Dispatches an email via SMTP."""
        if not cls.is_configured():
            return False, "SMTP is not configured."

        sender_email = settings.smtp_from_email or settings.smtp_user
        sender_name = settings.smtp_from_name or "Kangra Hub Free Tally XML"
        from_header = f"{sender_name} <{sender_email}>"

        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = from_header
        msg["To"] = to_email

        msg.attach(MIMEText(body_text, "plain", "utf-8"))
        if html_content:
            msg.attach(MIMEText(html_content, "html", "utf-8"))

        try:
            if settings.smtp_use_ssl or settings.smtp_port == 465:
                context = ssl.create_default_context()
                server = smtplib.SMTP_SSL(settings.smtp_host, settings.smtp_port, context=context, timeout=12)
            else:
                server = smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=12)
                if settings.smtp_use_tls:
                    context = ssl.create_default_context()
                    server.starttls(context=context)

            if settings.smtp_user and settings.smtp_password:
                server.login(settings.smtp_user, settings.smtp_password)

            server.sendmail(sender_email, [to_email], msg.as_string())
            server.quit()
            return True, "Email dispatched successfully."
        except Exception as exc:
            logger.error(f"Failed to dispatch email to {to_email}: {exc}")
            return False, f"Failed to send email: {str(exc)}"

    @classmethod
    def send_otp_email(
        cls,
        recipient_email: str,
        token: str,
        recipient_name: Optional[str] = None
    ) -> Tuple[bool, str]:
        """
        Dispatches verification OTP email according to PRD Section 7.
        Subject: Your Kangra Hub Verification Code
        Body:
            Your Kangra Hub verification code is:
            {{ .Token }}
            This code is valid for a limited time. If you did not request this code, you can safely ignore this email.
        """
        if not cls.is_configured():
            return False, "SMTP is not configured on the server."

        sender_email = settings.smtp_from_email or settings.smtp_user
        sender_name = settings.smtp_from_name or "Kangra Hub Free Tally XML"
        from_header = f"{sender_name} <{sender_email}>"

        subject = "Kangra Hub — Your Email Verification Code"

        text_content = (
            f"Hello {recipient_name or 'there'},\n\n"
            f"Your Kangra Hub verification code is:\n\n"
            f"    {token}\n\n"
            f"This code expires shortly (within 10 minutes). If you did not request this code, you can safely ignore this email.\n\n"
            f"— Kangra Hub Team"
        )

        html_content = f"""<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <title>{subject}</title>
</head>
<body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; background-color: #f8fafc; margin: 0; padding: 32px 16px; color: #0f172a;">
  <div style="max-width: 480px; margin: 0 auto; background: #ffffff; border-radius: 20px; border: 1px solid #e2e8f0; padding: 32px; box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.05);">
    <div style="margin-bottom: 24px; display: table; width: 100%;">
      <div style="display: table-cell; vertical-align: middle; width: 44px;">
        <img src="https://ueslsgzfixvkaomgogan.supabase.co/storage/v1/object/public/Logo/logo.png" alt="Kangra Hub" width="44" height="44" style="border-radius: 10px; display: block;" />
      </div>
      <div style="display: table-cell; vertical-align: middle; padding-left: 12px;">
        <h1 style="font-size: 20px; font-weight: 800; color: #0f172a; margin: 0 0 2px 0;">Kangra Hub</h1>
        <div style="font-size: 11px; font-weight: 700; color: #2563eb; text-transform: uppercase; letter-spacing: 0.05em;">Free Tally XML Platform</div>
      </div>
    </div>
    
    <div style="font-size: 14px; color: #334155; line-height: 1.6; margin-bottom: 20px;">
      Your Kangra Hub verification code is:
    </div>

    <div style="background-color: #f1f5f9; border: 1px solid #cbd5e1; border-radius: 12px; padding: 18px 24px; text-align: center; margin: 20px 0;">
      <span style="font-family: monospace, Courier, sans-serif; font-size: 32px; font-weight: 800; letter-spacing: 8px; color: #1e3a8a; display: inline-block;">
        {token}
      </span>
    </div>

    <div style="font-size: 12px; color: #64748b; line-height: 1.5; margin-top: 24px; border-top: 1px solid #f1f5f9; padding-top: 16px;">
      This code is valid for a limited time. If you did not request this code, you can safely ignore this email.
    </div>

    <div style="font-size: 11px; color: #94a3b8; margin-top: 24px;">
      &copy; Kangra Hub &bull; Bank Statement PDF to Tally XML
    </div>
  </div>
</body>
</html>
"""

        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = from_header
        msg["To"] = recipient_email

        msg.attach(MIMEText(text_content, "plain", "utf-8"))
        msg.attach(MIMEText(html_content, "html", "utf-8"))

        try:
            if settings.smtp_use_ssl or settings.smtp_port == 465:
                context = ssl.create_default_context()
                server = smtplib.SMTP_SSL(settings.smtp_host, settings.smtp_port, context=context, timeout=12)
            else:
                server = smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=12)
                if settings.smtp_use_tls:
                    context = ssl.create_default_context()
                    server.starttls(context=context)

            if settings.smtp_user and settings.smtp_password:
                server.login(settings.smtp_user, settings.smtp_password)

            server.sendmail(sender_email, [recipient_email], msg.as_string())
            server.quit()
            logger.info(f"Verification email dispatched successfully to {recipient_email}")
            return True, "Verification email dispatched successfully."
        except Exception as exc:
            logger.error(f"Failed to dispatch verification email to {recipient_email}: {exc}")
            return False, f"Failed to send email: {str(exc)}"

    @classmethod
    def send_suspension_email(
        cls,
        recipient_email: str,
        recipient_name: Optional[str] = None,
        reason: Optional[str] = None,
        deletion_date: Optional[str] = None
    ) -> Tuple[bool, str]:
        """Dispatches account suspension notification email according to PRD Section 16."""
        name = recipient_name or "Kangra Hub User"
        susp_reason = reason or "Policy and security compliance review."
        del_date = deletion_date or "3 months from today"

        subject = "Your Kangra Hub Account Has Been Suspended"

        text_content = (
            f"Hello {name},\n\n"
            f"Your Kangra Hub account has been suspended following an account/policy review.\n\n"
            f"Reason: {susp_reason}\n\n"
            f"While your account is suspended, you will not be able to access Kangra Hub services.\n\n"
            f"If you believe this suspension was made in error or would like to provide additional information, you can submit an appeal through the Kangra Hub login page.\n\n"
            f"Important: If the account remains suspended, it may be scheduled for deletion 3 months after the suspension date.\n\n"
            f"Scheduled deletion date: {del_date}\n\n"
            f"Regards,\n"
            f"Kangra Hub Administration"
        )

        html_content = f"""<!DOCTYPE html>
<html>
<head><meta charset="utf-8"><title>{subject}</title></head>
<body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; background-color: #f8fafc; margin: 0; padding: 32px 16px; color: #0f172a;">
  <div style="max-width: 520px; margin: 0 auto; background: #ffffff; border-radius: 20px; border: 1px solid #e2e8f0; padding: 32px; box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.05);">
    <div style="margin-bottom: 24px; display: table; width: 100%;">
      <div style="display: table-cell; vertical-align: middle; width: 44px;">
        <img src="https://ueslsgzfixvkaomgogan.supabase.co/storage/v1/object/public/Logo/logo.png" alt="Kangra Hub" width="44" height="44" style="border-radius: 10px; display: block;" />
      </div>
      <div style="display: table-cell; vertical-align: middle; padding-left: 12px;">
        <h1 style="font-size: 20px; font-weight: 800; color: #0f172a; margin: 0 0 2px 0;">Kangra Hub</h1>
        <div style="font-size: 11px; font-weight: 700; color: #dc2626; text-transform: uppercase; letter-spacing: 0.05em;">Account Status Notification</div>
      </div>
    </div>
    <div style="font-size: 14px; color: #334155; line-height: 1.6; margin-bottom: 16px;">
      Hello <strong>{name}</strong>,
    </div>
    <div style="font-size: 14px; color: #334155; line-height: 1.6; margin-bottom: 16px;">
      Your Kangra Hub account has been suspended following an account/policy review.
    </div>
    <div style="background-color: #fef2f2; border: 1px solid #fecaca; border-radius: 12px; padding: 14px 18px; margin: 16px 0;">
      <div style="font-size: 12px; font-weight: 700; color: #991b1b; margin-bottom: 4px;">Reason for Suspension:</div>
      <div style="font-size: 13px; color: #b91c1c;">{susp_reason}</div>
    </div>
    <div style="font-size: 13px; color: #475569; line-height: 1.6; margin-bottom: 16px;">
      While your account is suspended, you will not be able to access Kangra Hub conversion services or account features.
    </div>
    <div style="font-size: 13px; color: #475569; line-height: 1.6; margin-bottom: 16px;">
      If you believe this suspension was made in error or would like to provide additional information, you can submit an appeal through the Kangra Hub login page.
    </div>
    <div style="background-color: #fffbeb; border: 1px solid #fde68a; border-radius: 12px; padding: 14px 18px; margin: 16px 0;">
      <div style="font-size: 12px; font-weight: 700; color: #92400e; margin-bottom: 4px;">Important Deletion Notice:</div>
      <div style="font-size: 13px; color: #b45309; line-height: 1.5;">
        If your account remains suspended, it may be scheduled for deletion 3 months after the suspension date.<br/>
        <strong>Scheduled deletion date:</strong> {del_date}
      </div>
    </div>
    <div style="font-size: 13px; color: #334155; margin-top: 24px;">
      Regards,<br/>
      <strong>Kangra Hub Administration</strong>
    </div>
  </div>
</body>
</html>"""
        return cls.send_email(recipient_email, subject, text_content, html_content)

    @classmethod
    def send_recovery_email(
        cls,
        recipient_email: str,
        recipient_name: Optional[str] = None
    ) -> Tuple[bool, str]:
        """Dispatches account recovery notification email according to PRD Section 14."""
        name = recipient_name or "Kangra Hub User"
        subject = "Your Kangra Hub Account Has Been Recovered"

        text_content = (
            f"Hello {name},\n\n"
            f"We have completed the review of your Kangra Hub account.\n\n"
            f"Your account has been successfully recovered and you can now sign in and continue using Kangra Hub services.\n\n"
            f"Thank you for your patience while your account was under review.\n\n"
            f"Regards,\n"
            f"Kangra Hub Administration"
        )

        html_content = f"""<!DOCTYPE html>
<html>
<head><meta charset="utf-8"><title>{subject}</title></head>
<body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; background-color: #f8fafc; margin: 0; padding: 32px 16px; color: #0f172a;">
  <div style="max-width: 520px; margin: 0 auto; background: #ffffff; border-radius: 20px; border: 1px solid #e2e8f0; padding: 32px; box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.05);">
    <div style="margin-bottom: 24px; display: table; width: 100%;">
      <div style="display: table-cell; vertical-align: middle; width: 44px;">
        <img src="https://ueslsgzfixvkaomgogan.supabase.co/storage/v1/object/public/Logo/logo.png" alt="Kangra Hub" width="44" height="44" style="border-radius: 10px; display: block;" />
      </div>
      <div style="display: table-cell; vertical-align: middle; padding-left: 12px;">
        <h1 style="font-size: 20px; font-weight: 800; color: #0f172a; margin: 0 0 2px 0;">Kangra Hub</h1>
        <div style="font-size: 11px; font-weight: 700; color: #16a34a; text-transform: uppercase; letter-spacing: 0.05em;">Account Restored</div>
      </div>
    </div>
    <div style="font-size: 14px; color: #334155; line-height: 1.6; margin-bottom: 16px;">
      Hello <strong>{name}</strong>,
    </div>
    <div style="font-size: 14px; color: #334155; line-height: 1.6; margin-bottom: 16px;">
      We have completed the review of your Kangra Hub account.
    </div>
    <div style="background-color: #f0fdf4; border: 1px solid #bbf7d0; border-radius: 12px; padding: 16px 20px; margin: 16px 0;">
      <div style="font-size: 14px; font-weight: 700; color: #15803d; margin-bottom: 4px;">Account Successfully Recovered</div>
      <div style="font-size: 13px; color: #166534; line-height: 1.5;">
        Your account has been successfully recovered and you can now sign in and continue using Kangra Hub services.
      </div>
    </div>
    <div style="font-size: 13px; color: #475569; line-height: 1.6; margin-bottom: 16px;">
      Thank you for your patience while your account was under review.
    </div>
    <div style="font-size: 13px; color: #334155; margin-top: 24px;">
      Regards,<br/>
      <strong>Kangra Hub Administration</strong>
    </div>
  </div>
</body>
</html>"""
        return cls.send_email(recipient_email, subject, text_content, html_content)

    @classmethod
    def send_appeal_rejection_email(
        cls,
        recipient_email: str,
        recipient_name: Optional[str] = None,
        admin_response: Optional[str] = None,
        deletion_date: Optional[str] = None
    ) -> Tuple[bool, str]:
        """Dispatches appeal decision notification email according to PRD Section 17."""
        name = recipient_name or "Kangra Hub User"
        resp = admin_response or "After reviewing the submitted information, the account will remain suspended in accordance with security policies."
        del_date = deletion_date or "3 months from original suspension date"

        subject = "Update Regarding Your Kangra Hub Account Appeal"

        text_content = (
            f"Hello {name},\n\n"
            f"We have reviewed your request regarding your suspended Kangra Hub account.\n\n"
            f"After reviewing the information provided, your account will remain suspended at this time.\n\n"
            f"Review response: {resp}\n\n"
            f"Your account will remain inaccessible while the suspension is active.\n\n"
            f"Important: If the account remains suspended, it may be scheduled for deletion 3 months after the suspension date.\n\n"
            f"Scheduled deletion date: {del_date}\n\n"
            f"Regards,\n"
            f"Kangra Hub Administration"
        )

        html_content = f"""<!DOCTYPE html>
<html>
<head><meta charset="utf-8"><title>{subject}</title></head>
<body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; background-color: #f8fafc; margin: 0; padding: 32px 16px; color: #0f172a;">
  <div style="max-width: 520px; margin: 0 auto; background: #ffffff; border-radius: 20px; border: 1px solid #e2e8f0; padding: 32px; box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.05);">
    <div style="margin-bottom: 24px; display: table; width: 100%;">
      <div style="display: table-cell; vertical-align: middle; width: 44px;">
        <img src="https://ueslsgzfixvkaomgogan.supabase.co/storage/v1/object/public/Logo/logo.png" alt="Kangra Hub" width="44" height="44" style="border-radius: 10px; display: block;" />
      </div>
      <div style="display: table-cell; vertical-align: middle; padding-left: 12px;">
        <h1 style="font-size: 20px; font-weight: 800; color: #0f172a; margin: 0 0 2px 0;">Kangra Hub</h1>
        <div style="font-size: 11px; font-weight: 700; color: #ea580c; text-transform: uppercase; letter-spacing: 0.05em;">Appeal Review Decision</div>
      </div>
    </div>
    <div style="font-size: 14px; color: #334155; line-height: 1.6; margin-bottom: 16px;">
      Hello <strong>{name}</strong>,
    </div>
    <div style="font-size: 14px; color: #334155; line-height: 1.6; margin-bottom: 16px;">
      We have reviewed your request regarding your suspended Kangra Hub account.
    </div>
    <div style="font-size: 14px; color: #334155; line-height: 1.6; margin-bottom: 16px;">
      After reviewing the information provided, your account will remain suspended at this time.
    </div>
    <div style="background-color: #fff7ed; border: 1px solid #fed7aa; border-radius: 12px; padding: 14px 18px; margin: 16px 0;">
      <div style="font-size: 12px; font-weight: 700; color: #9a3412; margin-bottom: 4px;">Review Response:</div>
      <div style="font-size: 13px; color: #c2410c; line-height: 1.5;">{resp}</div>
    </div>
    <div style="font-size: 13px; color: #475569; line-height: 1.6; margin-bottom: 16px;">
      Your account will remain inaccessible while the suspension is active.
    </div>
    <div style="background-color: #fffbeb; border: 1px solid #fde68a; border-radius: 12px; padding: 14px 18px; margin: 16px 0;">
      <div style="font-size: 12px; font-weight: 700; color: #92400e; margin-bottom: 4px;">Important Deletion Notice:</div>
      <div style="font-size: 13px; color: #b45309; line-height: 1.5;">
        If your account remains suspended, it may be scheduled for deletion 3 months after the suspension date.<br/>
        <strong>Scheduled deletion date:</strong> {del_date}
      </div>
    </div>
    <div style="font-size: 13px; color: #334155; margin-top: 24px;">
      Regards,<br/>
      <strong>Kangra Hub Administration</strong>
    </div>
  </div>
</body>
</html>"""
        return cls.send_email(recipient_email, subject, text_content, html_content)

smtp_service = SMTPService()
