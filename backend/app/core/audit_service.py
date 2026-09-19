import json
import logging
import urllib.request
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field
from app.core.config import settings

logger = logging.getLogger("kangra_hub.audit")

class AuditLogEntry(BaseModel):
    id: str
    timestamp: str
    action: str
    user_id: Optional[str] = None
    target_type: Optional[str] = None
    target_id: Optional[str] = None
    result: str = "SUCCESS"  # "SUCCESS", "FAILURE", "BLOCKED"
    reason: Optional[str] = None
    ip_address: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)

class AuditLogService:
    """
    Production-grade audit logging service for Kangra Hub.
    Records critical security, authentication, admin, and recovery events.
    Persists events in both volatile memory and database (public.audit_logs).
    """

    def __init__(self):
        self._logs: List[AuditLogEntry] = []

    def log_event(
        self,
        action: str,
        user_id: Optional[str] = None,
        target_type: Optional[str] = None,
        target_id: Optional[str] = None,
        result: str = "SUCCESS",
        reason: Optional[str] = None,
        ip_address: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> AuditLogEntry:
        import uuid
        entry = AuditLogEntry(
            id=f"audit-{uuid.uuid4().hex[:12]}",
            timestamp=datetime.now(timezone.utc).isoformat(),
            action=action,
            user_id=user_id,
            target_type=target_type,
            target_id=target_id,
            result=result,
            reason=reason,
            ip_address=ip_address,
            metadata=metadata or {}
        )

        self._logs.append(entry)
        if len(self._logs) > 1000:
            self._logs = self._logs[-1000:]

        logger.info(f"[AUDIT] Action: {action} | User: {user_id} | Result: {result} | Reason: {reason}")

        # Attempt asynchronous/safe push to database public.audit_logs if Supabase configured
        from app.core.supabase_service import SupabaseService
        if SupabaseService.is_configured() and settings.supabase_service_role_key:
            try:
                url = f"{settings.supabase_url.rstrip('/')}/rest/v1/audit_logs"
                payload = json.dumps({
                    "action": action,
                    "admin_user_id": user_id if action.startswith("ADMIN") else None,
                    "target_type": target_type,
                    "target_id": target_id,
                    "metadata": {
                        **(metadata or {}),
                        "result": result,
                        "reason": reason
                    },
                    "ip_address": ip_address
                }).encode("utf-8")
                headers = {
                    "apikey": SupabaseService.get_api_key(),
                    "Authorization": f"Bearer {settings.supabase_service_role_key}",
                    "Content-Type": "application/json",
                    "Prefer": "return=minimal"
                }
                req = urllib.request.Request(url, data=payload, headers=headers, method="POST")
                with urllib.request.urlopen(req, timeout=4) as _:
                    pass
            except Exception as e:
                logger.debug(f"Audit log DB sync skipped: {e}")

        return entry

    def get_logs(
        self,
        limit: int = 100,
        action: Optional[str] = None,
        user_id: Optional[str] = None
    ) -> List[AuditLogEntry]:
        filtered = self._logs
        if action and action != "ALL":
            filtered = [l for l in filtered if l.action == action]
        if user_id:
            filtered = [l for l in filtered if l.user_id == user_id]
        return list(reversed(filtered[-limit:]))

audit_service = AuditLogService()
