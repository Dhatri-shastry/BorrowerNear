from datetime import datetime, timedelta, timezone

import jwt
from pwdlib import PasswordHash

from app.config import get_settings

password_hasher = PasswordHash.recommended()


def hash_password(password: str) -> str:
    return password_hasher.hash(password)


def verify_password(password: str, stored_hash: str) -> bool:
    try:
        return password_hasher.verify(password, stored_hash)
    except (ValueError, TypeError):
        return False


def create_access_token(user_id: int, role: str) -> str:
    s = get_settings()
    if len(s.jwt_secret) < 32:
        raise RuntimeError("JWT_SECRET must be at least 32 characters")
    now = datetime.now(timezone.utc)
    return jwt.encode({"sub": str(user_id), "role": role, "iat": now,
                       "exp": now + timedelta(minutes=s.access_token_minutes)},
                      s.jwt_secret, algorithm=s.jwt_algorithm)
