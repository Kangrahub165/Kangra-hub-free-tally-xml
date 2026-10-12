import pytest
from fastapi.testclient import TestClient
from main import app, origins_set

@pytest.fixture
def client():
    return TestClient(app)

def test_deploy_preview_origin_in_allowed_origins():
    deploy_preview = "https://deploy-preview-1--kangrahubtallyxml.netlify.app"
    assert deploy_preview in origins_set
    assert "https://kangrahubtallyxml.netlify.app" in origins_set

def test_cors_options_preflight_upload(client):
    origin = "https://deploy-preview-1--kangrahubtallyxml.netlify.app"
    headers = {
        "Origin": origin,
        "Access-Control-Request-Method": "POST",
        "Access-Control-Request-Headers": "Authorization, Content-Type",
    }
    response = client.options("/api/conversions/upload", headers=headers)
    assert response.status_code == 200
    assert response.headers.get("access-control-allow-origin") == origin
    assert response.headers.get("access-control-allow-credentials") == "true"
    assert "POST" in response.headers.get("access-control-allow-methods", "")

def test_cors_error_response_contains_headers(client):
    origin = "https://deploy-preview-1--kangrahubtallyxml.netlify.app"
    # Unauthenticated upload attempt should return 401 with CORS headers
    response = client.post(
        "/api/conversions/upload",
        headers={"Origin": origin},
        data={"password": "test"}
    )
    assert response.status_code == 401
    assert response.headers.get("access-control-allow-origin") == origin
    assert response.headers.get("access-control-allow-credentials") == "true"

def test_cors_404_error_contains_headers(client):
    origin = "https://deploy-preview-1--kangrahubtallyxml.netlify.app"
    response = client.get("/api/non-existent-endpoint", headers={"Origin": origin})
    assert response.status_code == 404
    assert response.headers.get("access-control-allow-origin") == origin
    assert response.headers.get("access-control-allow-credentials") == "true"

def test_cors_arbitrary_netlify_preview_allowed(client):
    origin = "https://deploy-preview-42--kangrahubtallyxml.netlify.app"
    headers = {
        "Origin": origin,
        "Access-Control-Request-Method": "POST",
        "Access-Control-Request-Headers": "Authorization, Content-Type",
    }
    response = client.options("/api/conversions/upload", headers=headers)
    assert response.status_code == 200
    assert response.headers.get("access-control-allow-origin") == origin
    assert response.headers.get("access-control-allow-credentials") == "true"

def test_cors_origins_env_read(monkeypatch):
    import os
    from app.core.config import Settings
    monkeypatch.setenv("CORS_ORIGINS", "https://custom-domain.example.com,https://other.example.com")
    new_settings = Settings()
    assert "https://custom-domain.example.com" in new_settings.cors_origins
    assert "https://custom-domain.example.com" in new_settings.allowed_origins

