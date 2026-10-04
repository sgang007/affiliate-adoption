from datetime import datetime, timedelta

import jwt
from passlib.hash import pbkdf2_sha256

from .config import get_settings

settings = get_settings()


def hash_password(password: str) -> str:
    return pbkdf2_sha256.hash(password)


def verify_password(password: str, hashed: str) -> bool:
    try:
        return pbkdf2_sha256.verify(password, hashed)
    except ValueError:
        return False


def create_access_token(user_id: int, role: str) -> str:
    payload = {
        "sub": str(user_id),
        "role": role,
        "exp": datetime.utcnow() + timedelta(minutes=settings.jwt_expire_minutes),
        "iat": datetime.utcnow(),
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def decode_token(token: str) -> dict:
    return jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
