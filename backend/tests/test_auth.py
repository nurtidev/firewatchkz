"""
tests/test_auth.py — Unit tests for JWT RBAC (task J-1).

All tests are fully mocked — no live DB or network calls required.
"""
import sys
import os

# Ensure the backend package root is on sys.path when running from the repo root
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from jose import jwt


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_auth_app(db_override=None):
    """Minimal app with only the v2 auth router registered."""
    from fastapi import FastAPI
    from routers.v2.auth import router as auth_router
    from db.session import get_db

    app = FastAPI()
    app.include_router(auth_router, prefix="/api/v2/auth")
    if db_override:
        app.dependency_overrides[get_db] = db_override
    return app


def _make_docs_app(db_override=None, current_user_override=None):
    """Minimal app with only the v2 documents router (for RBAC tests)."""
    from fastapi import FastAPI
    from routers.v2.documents import router as docs_router
    from db.session import get_db
    from services.auth import get_current_user

    app = FastAPI()
    app.include_router(docs_router, prefix="/api/v2/documents")
    if db_override:
        app.dependency_overrides[get_db] = db_override
    if current_user_override:
        app.dependency_overrides[get_current_user] = current_user_override
    return app


# ---------------------------------------------------------------------------
# Test 1 — create_access_token embeds sub and role in the payload
# ---------------------------------------------------------------------------


def test_create_access_token_contains_subject():
    """Token payload must contain 'sub' equal to the given user_id and the role."""
    from services.auth import create_access_token, SECRET_KEY, ALGORITHM

    token = create_access_token({"sub": "user-1", "role": "analyst"})

    payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])

    assert payload["sub"] == "user-1", "sub should equal the user_id passed in"
    assert "role" in payload, "role should be present in payload"
    assert payload["role"] == "analyst"


# ---------------------------------------------------------------------------
# Test 2 — verify_password returns True for the correct password
# ---------------------------------------------------------------------------


def test_verify_password_correct():
    """hash_password + verify_password round-trip must succeed."""
    from services.auth import hash_password, verify_password

    plain = "correct-horse-battery-staple"
    hashed = hash_password(plain)

    assert verify_password(plain, hashed) is True


# ---------------------------------------------------------------------------
# Test 3 — verify_password returns False for wrong password
# ---------------------------------------------------------------------------


def test_verify_password_wrong():
    """verify_password must return False when the password does not match."""
    from services.auth import hash_password, verify_password

    hashed = hash_password("secret")

    assert verify_password("wrong-password", hashed) is False


# ---------------------------------------------------------------------------
# Test 4 — login with dev placeholder hash accepts any password (200 + token)
# ---------------------------------------------------------------------------


def test_login_dev_placeholder_hash():
    """POST /api/v2/auth/token with a seeded placeholder-hash user must return 200."""
    # Build a mock DB row that mimics the seeded admin user
    mock_row = {
        "id": "user-admin-1",
        "email": "admin@firewatch.kz",
        "role": "admin",
        "password_hash": "$2b$12$placeholder_admin",
    }

    # Mock the DB session so it returns the fake row
    mock_result = MagicMock()
    mock_result.mappings.return_value.first.return_value = mock_row

    mock_session = AsyncMock()
    mock_session.execute = AsyncMock(return_value=mock_result)

    async def db_override():
        yield mock_session

    app = _make_auth_app(db_override=db_override)
    client = TestClient(app)

    response = client.post(
        "/api/v2/auth/token",
        data={"username": "admin@firewatch.kz", "password": "any-password-works"},
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert "access_token" in body
    assert body["token_type"] == "bearer"
    assert body["user_id"] == "user-admin-1"
    assert body["role"] == "admin"


# ---------------------------------------------------------------------------
# Test 5 — require_role returns 403 when the user's role is insufficient
# ---------------------------------------------------------------------------


def test_require_role_forbidden():
    """A viewer hitting an analyst-only endpoint must receive HTTP 403."""
    # Stub DB session (documents router needs one even though we'll override auth)
    mock_session = AsyncMock()

    async def db_override():
        yield mock_session

    # Inject a viewer as the current_user — bypasses real JWT validation
    def viewer_user():
        return {"id": "u1", "email": "v@test.kz", "full_name": "Viewer", "role": "viewer"}

    # Stub storage so upload_document doesn't crash when it instantiates storage
    with patch("routers.v2.documents.get_storage"):
        app = _make_docs_app(
            db_override=db_override,
            current_user_override=viewer_user,
        )
        client = TestClient(app, raise_server_exceptions=False)

        # POST /{card_id}/approve requires analyst_or_above → viewer must get 403
        response = client.post(
            "/api/v2/documents/some-card-id/approve",
            json={"approved_by": "u1"},
        )

    assert response.status_code == 403, response.text
    assert "роль" in response.json()["detail"].lower()
