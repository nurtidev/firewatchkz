from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
from typing import Optional

from fastapi import HTTPException

USERS = [
    {"email": "admin@firewatch.kz", "password": "admin123", "role": "admin"},
    {"email": "analyst@firewatch.kz", "password": "analyst123", "role": "analyst"},
    {"email": "dispatcher@firewatch.kz", "password": "dispatch123", "role": "dispatcher"},
    {"email": "viewer@firewatch.kz", "password": "viewer123", "role": "viewer"},
]


class AuthService:
    def login(self, email: str, password: str) -> dict:
        user = next((candidate for candidate in USERS if candidate["email"] == email), None)
        if not user or user["password"] != password:
            raise HTTPException(status_code=401, detail="Invalid credentials")

        safe_user = {"email": user["email"], "role": user["role"]}
        return {
            "token": self._sign_token(safe_user),
            "user": safe_user,
        }

    def get_current_user(self, authorization: Optional[str]) -> dict:
        if not authorization or not authorization.startswith("Bearer "):
            raise HTTPException(status_code=401, detail="Missing bearer token")

        token = authorization.removeprefix("Bearer ").strip()
        payload = self._verify_token(token)
        if not payload:
            raise HTTPException(status_code=401, detail="Invalid token")
        return payload

    def _sign_token(self, payload: dict) -> str:
        secret = os.getenv("AUTH_SECRET", "firewatch-dev-secret")
        payload_json = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")
        encoded_payload = base64.urlsafe_b64encode(payload_json).decode("utf-8").rstrip("=")
        signature = hmac.new(secret.encode("utf-8"), encoded_payload.encode("utf-8"), hashlib.sha256).hexdigest()
        return f"{encoded_payload}.{signature}"

    def _verify_token(self, token: str) -> Optional[dict]:
        if "." not in token:
            return None
        encoded_payload, signature = token.split(".", 1)
        secret = os.getenv("AUTH_SECRET", "firewatch-dev-secret")
        expected_signature = hmac.new(
            secret.encode("utf-8"),
            encoded_payload.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()
        if not hmac.compare_digest(signature, expected_signature):
            return None

        padding = "=" * (-len(encoded_payload) % 4)
        payload_json = base64.urlsafe_b64decode(f"{encoded_payload}{padding}".encode("utf-8")).decode("utf-8")
        payload = json.loads(payload_json)
        if not isinstance(payload, dict) or "email" not in payload or "role" not in payload:
            return None
        return {"email": payload["email"], "role": payload["role"]}


auth_service = AuthService()
