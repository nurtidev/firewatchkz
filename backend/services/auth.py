"""
services/auth.py — JWT issuance and RBAC dependency factories.

Usage:
    from services.auth import get_current_user, require_role, require_admin, require_analyst_or_above, require_inspector_or_above
"""
import os
from datetime import datetime, timedelta, timezone
from typing import List, Optional

from fastapi import Depends, HTTPException
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from db.session import get_db

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

SECRET_KEY = os.environ.get("JWT_SECRET_KEY", "dev-secret-change-in-production")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 8  # 8 hours

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v2/auth/token", auto_error=False)


# ---------------------------------------------------------------------------
# Password utilities
# ---------------------------------------------------------------------------


def verify_password(plain: str, hashed: str) -> bool:
    """Return True if *plain* matches the bcrypt *hashed* password."""
    return pwd_context.verify(plain, hashed)


def hash_password(plain: str) -> str:
    """Return a bcrypt hash of *plain*."""
    return pwd_context.hash(plain)


# ---------------------------------------------------------------------------
# Token utilities
# ---------------------------------------------------------------------------


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """Create a signed JWT containing *data* with an expiry."""
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + (
        expires_delta if expires_delta is not None
        else timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


# ---------------------------------------------------------------------------
# FastAPI dependency — authenticate
# ---------------------------------------------------------------------------


async def get_current_user(
    token: Optional[str] = Depends(oauth2_scheme),
    session: AsyncSession = Depends(get_db),
) -> dict:
    """Decode JWT and return user dict with id, email, full_name, role.

    Raises HTTP 401 when the token is missing or invalid.
    """
    if not token:
        raise HTTPException(status_code=401, detail="Требуется авторизация")

    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id: Optional[str] = payload.get("sub")
        if not user_id:
            raise HTTPException(status_code=401, detail="Недействительный токен")
    except JWTError:
        raise HTTPException(status_code=401, detail="Недействительный токен")

    result = await session.execute(
        text("SELECT id, email, full_name, role FROM users WHERE id = :id"),
        {"id": user_id},
    )
    user = result.mappings().first()
    if not user:
        raise HTTPException(status_code=401, detail="Пользователь не найден")

    return dict(user)


# ---------------------------------------------------------------------------
# FastAPI dependency factory — authorise
# ---------------------------------------------------------------------------


def require_role(*roles: str):
    """Return a FastAPI dependency that ensures the current user has one of *roles*.

    Usage::

        @router.post("/sensitive")
        async def endpoint(user: dict = Depends(require_role("admin", "analyst"))):
            ...
    """
    async def _check(user: dict = Depends(get_current_user)) -> dict:
        if user["role"] not in roles:
            raise HTTPException(
                status_code=403,
                detail=f"Требуется роль: {', '.join(roles)}",
            )
        return user

    return _check


# ---------------------------------------------------------------------------
# Convenience shortcuts
# ---------------------------------------------------------------------------

require_admin = require_role("admin")
require_analyst_or_above = require_role("admin", "analyst")
require_inspector_or_above = require_role("admin", "analyst", "inspector")
