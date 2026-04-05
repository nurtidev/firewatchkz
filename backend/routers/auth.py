from typing import Optional

from fastapi import APIRouter
from fastapi import Header
from pydantic import BaseModel

from services.auth_service import auth_service

router = APIRouter(prefix="/auth", tags=["auth"])


class LoginRequest(BaseModel):
    email: str
    password: str


@router.post("/login")
def login(payload: LoginRequest) -> dict:
    return auth_service.login(payload.email, payload.password)


@router.get("/me")
def me(authorization: Optional[str] = Header(None)) -> dict:
    return {"user": auth_service.get_current_user(authorization)}
