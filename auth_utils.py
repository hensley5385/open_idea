from passlib.context import CryptContext
import base64
import hashlib
import hmac
import json
import os
import time
from typing import Any, Optional

# Use a widely-supported scheme that doesn't require native bcrypt bindings.
# This keeps local dev and CI stable across platforms/Python versions.
pwd_context = CryptContext(schemes=["pbkdf2_sha256"], deprecated="auto")

def hash_password(password: str):
    return pwd_context.hash(password)

def verify_password(plain_password: str, hashed_password: str):
    if not hashed_password:
        return False
    return pwd_context.verify(plain_password, hashed_password)

# --- Signed session tokens (HMAC) ---

SESSION_COOKIE_NAME = "bridge_session"

def _b64url_encode(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).decode("utf-8").rstrip("=")

def _b64url_decode(data: str) -> bytes:
    padding = "=" * (-len(data) % 4)
    return base64.urlsafe_b64decode((data + padding).encode("utf-8"))

def _get_app_secret() -> bytes:
    secret = os.getenv("APP_SECRET_KEY", "").strip()
    if not secret:
        # Dev fallback; override in production.
        secret = "dev-insecure-change-me"
    return secret.encode("utf-8")

def _sign(payload_bytes: bytes) -> str:
    return hmac.new(_get_app_secret(), payload_bytes, hashlib.sha256).hexdigest()

def create_signed_token(payload: dict[str, Any], ttl_seconds: int) -> str:
    data = dict(payload)
    now = int(time.time())
    data["iat"] = now
    data["exp"] = now + int(ttl_seconds)
    body = json.dumps(data, separators=(",", ":"), sort_keys=True).encode("utf-8")
    sig = _sign(body).encode("utf-8")
    return f"{_b64url_encode(body)}.{_b64url_encode(sig)}"

def read_signed_token(token: str) -> Optional[dict[str, Any]]:
    try:
        body_b64, sig_b64 = token.split(".", 1)
        body = _b64url_decode(body_b64)
        sig = _b64url_decode(sig_b64)
        expected = _sign(body).encode("utf-8")
        if not hmac.compare_digest(sig, expected):
            return None
        data = json.loads(body.decode("utf-8"))
        exp = int(data.get("exp", 0))
        if exp and int(time.time()) > exp:
            return None
        return data
    except Exception:
        return None

def create_user_session(user_id: int, role: str, ttl_seconds: int = 60 * 60 * 24 * 7) -> str:
    return create_signed_token({"user_id": int(user_id), "role": str(role)}, ttl_seconds=ttl_seconds)

def read_user_session(token: str) -> Optional[dict[str, Any]]:
    data = read_signed_token(token)
    if not data:
        return None
    if "user_id" not in data or "role" not in data:
        return None
    return {"user_id": int(data["user_id"]), "role": str(data["role"])}

