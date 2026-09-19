import pytest
from typing import Optional
from fastapi import Header, Query, HTTPException
from app.core.security import get_current_user, CurrentUser
from main import app

@pytest.fixture(autouse=True)
def setup_test_auth_override():
    original_override = app.dependency_overrides.get(get_current_user)

    async def test_get_current_user(
        authorization: Optional[str] = Header(None),
        token: Optional[str] = Query(None)
    ):
        raw_token = None
        if authorization:
            scheme, _, bearer_token = authorization.partition(" ")
            if scheme.lower() == "bearer" and bearer_token:
                raw_token = bearer_token
        elif token:
            raw_token = token

        if not raw_token:
            raise HTTPException(status_code=401, detail="Authentication required. Please log in.")

        if raw_token in ("mock-admin-token", "admin"):
            return CurrentUser(
                id="test-admin-id",
                email="admin@tallyxml.in",
                role="ADMIN",
                is_unlimited=True,
                full_name="Admin TallyXML"
            )
        elif raw_token in ("mock-user-token", "user"):
            user_id = "test-user-id"
            email = "user@example.com"
            from app.core.user_store import get_user_suspension_info
            s_info = get_user_suspension_info(user_id) or get_user_suspension_info(email) or {}
            if s_info.get("is_suspended"):
                raise HTTPException(
                    status_code=403,
                    detail={
                        "error": "ACCOUNT_SUSPENDED",
                        "code": "ACCOUNT_SUSPENDED",
                        "message": "Your Kangra Hub account has been temporarily suspended due to a policy or account-related issue.",
                        "user_id": user_id,
                        "email": email,
                        "full_name": s_info.get("full_name") or "Test Standard User",
                        "suspension_reason": s_info.get("suspension_reason"),
                        "suspended_at": s_info.get("suspended_at"),
                        "suspension_delete_at": s_info.get("suspension_delete_at")
                    }
                )
            return CurrentUser(
                id="test-user-id",
                email="user@example.com",
                role="USER",
                is_unlimited=False,
                full_name="Test Standard User"
            )
        elif raw_token in ("mock-unlimited-token", "unlimited"):
            return CurrentUser(
                id="test-unlimited-id",
                email="unlimited@example.com",
                role="USER",
                is_unlimited=True,
                full_name="Test Unlimited User"
            )
        else:
            from app.core.security import get_current_user as real_get_current_user
            return await real_get_current_user(authorization=authorization, token=token)

    app.dependency_overrides[get_current_user] = test_get_current_user
    yield
    if original_override:
        app.dependency_overrides[get_current_user] = original_override
    else:
        app.dependency_overrides.pop(get_current_user, None)
