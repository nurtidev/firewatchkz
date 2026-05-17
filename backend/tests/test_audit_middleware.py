"""
tests/test_audit_middleware.py — Unit tests for the AuditMiddleware (task J-2).

All tests are fully mocked — no live DB or network calls required.
"""
import sys
import os

# Ensure backend package root is on sys.path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from jose import jwt

# ---------------------------------------------------------------------------
# Import helpers we test directly (pure functions, no DB)
# ---------------------------------------------------------------------------

from middleware.audit import (
    _should_log,
    _infer_entity_type,
    _extract_entity_id,
    _extract_user_id,
    MUTATION_METHODS,
    SKIP_PREFIXES,
)
from services.auth import SECRET_KEY, ALGORITHM, create_access_token


# ===========================================================================
# 1. _should_log — method filtering
# ===========================================================================


class TestShouldLog:
    def test_post_is_logged(self):
        assert _should_log("POST", "/api/v2/documents/upload") is True

    def test_patch_is_logged(self):
        assert _should_log("PATCH", "/api/v2/buildings/abc123") is True

    def test_put_is_logged(self):
        assert _should_log("PUT", "/api/v1/incidents/1") is True

    def test_delete_is_logged(self):
        assert _should_log("DELETE", "/api/v2/documents/some-id") is True

    def test_get_is_not_logged(self):
        assert _should_log("GET", "/api/v2/documents/") is False

    def test_head_is_not_logged(self):
        assert _should_log("HEAD", "/api/v2/documents/") is False

    def test_options_is_not_logged(self):
        assert _should_log("OPTIONS", "/api/v2/documents/") is False

    def test_method_case_insensitive(self):
        assert _should_log("post", "/api/v2/buildings") is True
        assert _should_log("get", "/api/v1/cities") is False


# ===========================================================================
# 2. _should_log — skip-prefix filtering
# ===========================================================================


class TestShouldLogSkipPrefixes:
    def test_auth_routes_skipped(self):
        assert _should_log("POST", "/api/v2/auth/token") is False
        assert _should_log("POST", "/api/v2/auth/register") is False

    def test_health_skipped(self):
        assert _should_log("GET", "/health") is False
        # Even if someone POSTs to /health
        assert _should_log("POST", "/health") is False

    def test_metrics_skipped(self):
        assert _should_log("POST", "/metrics") is False

    def test_docs_skipped(self):
        assert _should_log("GET", "/docs") is False
        assert _should_log("POST", "/docs/something") is False

    def test_openapi_skipped(self):
        assert _should_log("GET", "/openapi.json") is False

    def test_regular_api_not_skipped(self):
        assert _should_log("POST", "/api/v1/incidents") is True
        assert _should_log("DELETE", "/api/v2/buildings/x") is True


# ===========================================================================
# 3. _infer_entity_type — URL → entity_type mapping
# ===========================================================================


class TestInferEntityType:
    def test_documents_path(self):
        assert _infer_entity_type("/api/v2/documents/upload") == "operational_cards"
        assert _infer_entity_type("/api/v2/documents/") == "operational_cards"
        assert _infer_entity_type("/api/v2/documents/abc-123/approve") == "operational_cards"

    def test_buildings_v2(self):
        assert _infer_entity_type("/api/v2/buildings") == "buildings"
        assert _infer_entity_type("/api/v2/buildings/some-id") == "buildings"

    def test_buildings_v1(self):
        assert _infer_entity_type("/api/v1/buildings") == "buildings"

    def test_incidents(self):
        assert _infer_entity_type("/api/v1/incidents") == "incidents"
        assert _infer_entity_type("/api/v2/incidents/42") == "incidents"

    def test_operations(self):
        assert _infer_entity_type("/api/v1/operations") == "operations"

    def test_hydrants(self):
        assert _infer_entity_type("/api/v1/hydrants") == "hydrants"

    def test_stations(self):
        assert _infer_entity_type("/api/v1/stations/5") == "stations"

    def test_unknown_path_falls_back(self):
        # For an unknown path the function should not crash — it returns something
        result = _infer_entity_type("/api/v1/unknown-resource")
        assert isinstance(result, str)
        assert len(result) > 0


# ===========================================================================
# 4. _extract_entity_id — last-segment ID extraction
# ===========================================================================


class TestExtractEntityId:
    def test_uuid_is_extracted(self):
        uuid_str = "550e8400-e29b-41d4-a716-446655440000"
        assert _extract_entity_id(f"/api/v2/documents/{uuid_str}") == uuid_str

    def test_numeric_id_is_extracted(self):
        assert _extract_entity_id("/api/v1/incidents/42") == "42"

    def test_verb_segment_returns_none(self):
        assert _extract_entity_id("/api/v2/documents/upload") is None
        assert _extract_entity_id("/api/v2/documents/some-id/approve") is None
        assert _extract_entity_id("/api/v2/documents/some-id/status") is None
        assert _extract_entity_id("/api/v2/documents/some-id/extraction") is None

    def test_collection_path_returns_none(self):
        # Last segment is "documents" — not UUID-like
        assert _extract_entity_id("/api/v2/documents") is None

    def test_trailing_slash_handled(self):
        # Trailing slash — last real segment is "documents"
        assert _extract_entity_id("/api/v2/documents/") is None

    def test_hex_id_is_extracted(self):
        # Long hex string (mongo-style)
        hex_id = "507f1f77bcf86cd799439011"
        assert _extract_entity_id(f"/api/v1/items/{hex_id}") == hex_id


# ===========================================================================
# 5. _extract_user_id — JWT decoding
# ===========================================================================


class TestExtractUserId:
    def test_valid_bearer_token(self):
        token = create_access_token({"sub": "user-admin-1", "role": "admin"})
        header = f"Bearer {token}"
        assert _extract_user_id(header) == "user-admin-1"

    def test_missing_header(self):
        assert _extract_user_id(None) is None

    def test_empty_header(self):
        assert _extract_user_id("") is None

    def test_non_bearer_scheme(self):
        assert _extract_user_id("Basic dXNlcjpwYXNz") is None

    def test_malformed_token(self):
        assert _extract_user_id("Bearer not.a.jwt") is None

    def test_token_without_sub(self):
        # Token with no 'sub' claim
        token = jwt.encode({"role": "admin"}, SECRET_KEY, algorithm=ALGORITHM)
        assert _extract_user_id(f"Bearer {token}") is None

    def test_token_signed_with_wrong_key(self):
        token = jwt.encode({"sub": "user-1"}, "wrong-secret", algorithm=ALGORITHM)
        assert _extract_user_id(f"Bearer {token}") is None


# ===========================================================================
# 6. AuditMiddleware integration — DB write is mocked
# ===========================================================================


class TestAuditMiddlewareIntegration:
    """
    These tests use FastAPI's TestClient + httpx to exercise the full
    middleware dispatch path, mocking only the DB write coroutine.
    """

    def _make_app(self):
        from fastapi import FastAPI
        from middleware.audit import AuditMiddleware

        app = FastAPI()
        app.add_middleware(AuditMiddleware)

        @app.get("/api/v1/buildings")
        async def get_buildings():
            return {"buildings": []}

        @app.post("/api/v1/buildings")
        async def create_building():
            return {"id": "new-building"}

        @app.delete("/api/v1/buildings/123")
        async def delete_building():
            return {"deleted": True}

        @app.post("/api/v2/auth/token")
        async def fake_login():
            return {"access_token": "tok"}

        @app.get("/health")
        async def health():
            return {"status": "ok"}

        return app

    @patch("middleware.audit._write_audit_log", new_callable=AsyncMock)
    def test_get_does_not_trigger_audit(self, mock_write):
        """GET requests must not schedule a DB write."""
        from fastapi.testclient import TestClient

        client = TestClient(self._make_app())
        resp = client.get("/api/v1/buildings")
        assert resp.status_code == 200
        # Give the event loop a moment — but since GET should not call it, stays 0
        mock_write.assert_not_called()

    @patch("middleware.audit._write_audit_log", new_callable=AsyncMock)
    def test_post_triggers_audit(self, mock_write):
        """POST to a non-skipped route must schedule one DB write."""
        import asyncio
        from fastapi.testclient import TestClient

        client = TestClient(self._make_app())
        resp = client.post("/api/v1/buildings")
        assert resp.status_code == 200
        # TestClient runs in synchronous mode; the create_task fires during the
        # request handling. Allow the event loop to process pending tasks.
        mock_write.assert_called_once()
        call_kwargs = mock_write.call_args
        # Positional args: user_id, action, entity_type, entity_id, ip_address
        args = call_kwargs[0]
        assert args[1] == "POST /api/v1/buildings"  # action
        assert args[2] == "buildings"               # entity_type

    @patch("middleware.audit._write_audit_log", new_callable=AsyncMock)
    def test_auth_route_is_skipped(self, mock_write):
        """POST to /api/v2/auth/... must NOT write an audit row."""
        from fastapi.testclient import TestClient

        client = TestClient(self._make_app())
        resp = client.post("/api/v2/auth/token")
        assert resp.status_code == 200
        mock_write.assert_not_called()

    @patch("middleware.audit._write_audit_log", new_callable=AsyncMock)
    def test_health_is_skipped(self, mock_write):
        """GET /health must not write an audit row."""
        from fastapi.testclient import TestClient

        client = TestClient(self._make_app())
        resp = client.get("/health")
        assert resp.status_code == 200
        mock_write.assert_not_called()

    @patch("middleware.audit._write_audit_log", new_callable=AsyncMock)
    def test_delete_extracts_entity_id(self, mock_write):
        """DELETE /api/v1/buildings/123 must set entity_id='123'."""
        from fastapi.testclient import TestClient

        client = TestClient(self._make_app())
        resp = client.delete("/api/v1/buildings/123")
        assert resp.status_code == 200
        mock_write.assert_called_once()
        args = mock_write.call_args[0]
        assert args[3] == "123"   # entity_id

    @patch("middleware.audit._write_audit_log", new_callable=AsyncMock)
    def test_db_failure_does_not_crash_request(self, mock_write):
        """Even if the DB write raises, the HTTP response must succeed."""
        mock_write.side_effect = Exception("DB connection lost")
        from fastapi.testclient import TestClient

        client = TestClient(self._make_app())
        resp = client.post("/api/v1/buildings")
        # Response must still be 200
        assert resp.status_code == 200
