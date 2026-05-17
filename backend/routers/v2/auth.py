"""
routers/v2/auth.py — Authentication endpoints (API v2).

POST /api/v2/auth/token  — OAuth2 password flow (form), returns access_token
POST /api/v2/auth/login  — JSON {email,password} → {token,user}  (frontend contract)
GET  /api/v2/auth/me     — Bearer token → {user}                 (frontend contract)
"""
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from db.session import get_db
from services.auth import create_access_token, get_current_user, verify_password

router = APIRouter()


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user_id: str
    role: str


class LoginPayload(BaseModel):
    email: str
    password: str


class UserPayload(BaseModel):
    email: str
    role: str


class LoginResponse(BaseModel):
    token: str
    user: UserPayload


class MeResponse(BaseModel):
    user: UserPayload


# ---------------------------------------------------------------------------
# Shared authentication helper
# ---------------------------------------------------------------------------


async def _authenticate(session: AsyncSession, email: str, password: str) -> dict:
    """Look up user by email and verify password; return the user mapping.

    Dev placeholder hashes ('$2b$12$placeholder…') accept any password so the
    seeded test accounts from migration 0002 can log in without bcrypt.
    """
    result = await session.execute(
        text("SELECT id, email, role, password_hash FROM users WHERE email = :email"),
        {"email": email},
    )
    user = result.mappings().first()
    if not user:
        raise HTTPException(status_code=401, detail="Неверный email или пароль")

    hashed: Optional[str] = user["password_hash"]
    if hashed and hashed.startswith("$2b$12$placeholder"):
        password_ok = True
    elif hashed:
        password_ok = verify_password(password, hashed)
    else:
        password_ok = False

    if not password_ok:
        raise HTTPException(status_code=401, detail="Неверный email или пароль")

    return dict(user)


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.post("/token", response_model=TokenResponse)
async def login_oauth2_form(
    form: OAuth2PasswordRequestForm = Depends(),
    session: AsyncSession = Depends(get_db),
) -> TokenResponse:
    """OAuth2 password flow — used by FastAPI Swagger and CLI tools."""
    user = await _authenticate(session, form.username, form.password)
    token = create_access_token({"sub": user["id"], "role": user["role"]})
    return TokenResponse(
        access_token=token,
        token_type="bearer",
        user_id=user["id"],
        role=user["role"],
    )


@router.post("/login", response_model=LoginResponse)
async def login_json(
    payload: LoginPayload,
    session: AsyncSession = Depends(get_db),
) -> LoginResponse:
    """JSON login flow — used by the Next.js frontend."""
    user = await _authenticate(session, payload.email, payload.password)
    token = create_access_token({"sub": user["id"], "role": user["role"]})
    return LoginResponse(
        token=token,
        user=UserPayload(email=user["email"], role=user["role"]),
    )


@router.get("/me", response_model=MeResponse)
async def me(user: dict = Depends(get_current_user)) -> MeResponse:
    """Return the authenticated user (from Bearer token)."""
    return MeResponse(user=UserPayload(email=user["email"], role=user["role"]))
