"""Single-user JWT auth.

Credentials come from env (.env at repo root):
  BACKEND_USER          login email
  BACKEND_PASSWORD_HASH bcrypt hash of the password
  BACKEND_JWT_SECRET    HS256 signing secret
  BACKEND_JWT_TTL_HOURS lifetime in hours (default 720 = 30 days)

Generate a password hash:
  python -c "from passlib.hash import bcrypt; print(bcrypt.hash('your-password'))"
"""

from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from passlib.hash import bcrypt

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth/login")


def _secret() -> str:
    s = os.environ.get("BACKEND_JWT_SECRET")
    if not s:
        raise RuntimeError("BACKEND_JWT_SECRET is not set")
    return s


def _ttl_hours() -> int:
    return int(os.environ.get("BACKEND_JWT_TTL_HOURS", "720"))


def verify_credentials(email: str, password: str) -> bool:
    expected_email = os.environ.get("BACKEND_USER")
    expected_hash = os.environ.get("BACKEND_PASSWORD_HASH")
    if not expected_email or not expected_hash:
        raise RuntimeError("BACKEND_USER / BACKEND_PASSWORD_HASH not set")
    if email.strip().lower() != expected_email.strip().lower():
        return False
    return bcrypt.verify(password, expected_hash)


def issue_token(subject: str) -> tuple[str, datetime]:
    expires_at = datetime.now(timezone.utc) + timedelta(hours=_ttl_hours())
    payload = {"sub": subject, "exp": expires_at}
    token = jwt.encode(payload, _secret(), algorithm="HS256")
    return token, expires_at


def require_user(token: str = Depends(oauth2_scheme)) -> str:
    try:
        payload = jwt.decode(token, _secret(), algorithms=["HS256"])
        sub = payload.get("sub")
        if not sub:
            raise JWTError("missing sub")
        return sub
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )
