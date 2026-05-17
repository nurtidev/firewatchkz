"""
middleware/audit.py — Starlette middleware that writes an audit_log row
for every mutating HTTP request (POST, PATCH, PUT, DELETE).

Design goals:
- DB write happens in a fire-and-forget asyncio task so overhead < 5 ms.
- Never raises an exception — all errors are printed to stderr.
- Python 3.9 compatible (uses typing.Optional / List / Union).
"""
import asyncio
import re
import sys
from typing import Optional

from jose import JWTError, jwt
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

import os

SECRET_KEY: str = os.environ.get("JWT_SECRET_KEY", "dev-secret-change-in-production")
ALGORITHM: str = "HS256"

# Methods that must be logged
MUTATION_METHODS = {"POST", "PATCH", "PUT", "DELETE"}

# Path prefixes that must NOT be logged
SKIP_PREFIXES = (
    "/api/v2/auth/",
    "/metrics",
    "/health",
    "/docs",
    "/openapi",
    "/redoc",
)

# ---------------------------------------------------------------------------
# Path → entity_type mapping
# Order matters — more specific patterns first.
# ---------------------------------------------------------------------------

_ENTITY_TYPE_MAP = [
    (re.compile(r"^/api/v2/documents"), "operational_cards"),
    (re.compile(r"^/api/v2/buildings"), "buildings"),
    (re.compile(r"^/api/v[12]/buildings"), "buildings"),
    (re.compile(r"^/api/v[12]/incidents"), "incidents"),
    (re.compile(r"^/api/v[12]/operations"), "operations"),
    (re.compile(r"^/api/v[12]/hydrants"), "hydrants"),
    (re.compile(r"^/api/v[12]/stations"), "stations"),
    (re.compile(r"^/api/v[12]/users"), "users"),
    (re.compile(r"^/api/v2/admin"), "audit_log"),
]

# Segments that look like verbs / sub-actions (not IDs)
_VERB_SEGMENTS = {
    "upload", "approve", "status", "extraction",
    "import", "export", "search", "bulk",
}

# Rough UUID-like pattern OR any numeric string → treat as entity ID
_ID_PATTERN = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$"
    r"|^[0-9]+$"
    r"|^[0-9a-f]{24,}$",  # mongo-style hex IDs
    re.IGNORECASE,
)


# ---------------------------------------------------------------------------
# Helper functions (pure — easily unit-tested)
# ---------------------------------------------------------------------------


def _should_log(method: str, path: str) -> bool:
    """Return True if this request should be written to the audit log."""
    if method.upper() not in MUTATION_METHODS:
        return False
    for prefix in SKIP_PREFIXES:
        if path.startswith(prefix):
            return False
    return True


def _infer_entity_type(path: str) -> str:
    """Map a URL path to a human-readable entity type string."""
    for pattern, entity_type in _ENTITY_TYPE_MAP:
        if pattern.match(path):
            return entity_type
    # Fallback: take the first meaningful path segment after /api/vN/
    parts = [p for p in path.split("/") if p]
    for i, part in enumerate(parts):
        if part.startswith("v") and len(part) <= 3:
            continue
        if part == "api":
            continue
        return part
    return "unknown"


def _extract_entity_id(path: str) -> Optional[str]:
    """Return the last path segment if it looks like an ID, otherwise None."""
    parts = [p for p in path.rstrip("/").split("/") if p]
    if not parts:
        return None
    last = parts[-1]
    if last.lower() in _VERB_SEGMENTS:
        return None
    if _ID_PATTERN.match(last):
        return last
    return None


def _extract_user_id(authorization: Optional[str]) -> Optional[str]:
    """Decode a Bearer JWT and return the 'sub' claim (user_id), or None."""
    if not authorization or not authorization.startswith("Bearer "):
        return None
    token = authorization[len("Bearer "):]
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload.get("sub")
    except JWTError:
        return None


# ---------------------------------------------------------------------------
# DB write (fire-and-forget coroutine)
# ---------------------------------------------------------------------------


async def _write_audit_log(
    user_id: Optional[str],
    action: str,
    entity_type: str,
    entity_id: Optional[str],
    ip_address: Optional[str],
) -> None:
    """Insert one row into audit_log. All errors are swallowed."""
    try:
        from db.session import AsyncSessionLocal  # local import avoids circular deps at import time

        async with AsyncSessionLocal() as session:
            from sqlalchemy import text

            await session.execute(
                text(
                    """
                    INSERT INTO audit_log
                        (user_id, action, entity_type, entity_id, ip_address, occurred_at)
                    VALUES
                        (:user_id, :action, :entity_type, :entity_id, :ip_address, NOW())
                    """
                ),
                {
                    "user_id": user_id,
                    "action": action,
                    "entity_type": entity_type,
                    "entity_id": entity_id,
                    "ip_address": ip_address,
                },
            )
            await session.commit()
    except Exception as exc:  # noqa: BLE001
        print(f"[audit_middleware] DB write failed: {exc}", file=sys.stderr)


# ---------------------------------------------------------------------------
# Middleware class
# ---------------------------------------------------------------------------


class AuditMiddleware(BaseHTTPMiddleware):
    """Log mutating requests to audit_log in a background task."""

    async def dispatch(self, request: Request, call_next) -> Response:  # type: ignore[override]
        response = await call_next(request)

        method = request.method.upper()
        path = request.url.path

        if not _should_log(method, path):
            return response

        action = f"{method} {path}"
        entity_type = _infer_entity_type(path)
        entity_id = _extract_entity_id(path)
        user_id = _extract_user_id(request.headers.get("authorization"))
        ip_address: Optional[str] = request.client.host if request.client else None

        # Fire-and-forget — response is already sent/streaming
        asyncio.create_task(
            _write_audit_log(user_id, action, entity_type, entity_id, ip_address)
        )

        return response
