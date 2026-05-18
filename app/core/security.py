import re
from datetime import datetime, timedelta, timezone
from typing import Any

import jwt
from pwdlib import PasswordHash

from app.core.config import get_settings

settings = get_settings()

password_hash = PasswordHash.recommended()


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return password_hash.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    return password_hash.hash(password)


MAX_PASSWORD_LENGTH = 128


def validate_password_complexity(password: str) -> None:
    """Raise ValueError if `password` doesn't meet the complexity rules.

    Rules: 8 to 128 chars, at least one uppercase letter, at least one
    digit, and at least one non-alphanumeric character. The upper bound
    is defense-in-depth against hash-DoS via multi-MB inputs.
    """
    if len(password) > MAX_PASSWORD_LENGTH:
        raise ValueError(f"Password must not exceed {MAX_PASSWORD_LENGTH} characters.")
    if (
        len(password) < 8
        or not re.search(r"[A-Z]", password)
        or not re.search(r"\d", password)
        or not re.search(r"[^A-Za-z0-9]", password)
    ):
        raise ValueError(
            "Password must be at least 8 characters and include an uppercase letter, a number, and a special character."
        )


def create_access_token(data: dict[str, str], expires_delta: timedelta | None = None) -> str:
    to_encode: dict[str, str | datetime] = dict(data)
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    encoded_jwt: str = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    return encoded_jwt


def decode_access_token(token: str) -> dict[str, Any]:
    """
    Decode and validate a JWT access token.

    Args:
        token: JWT token string

    Returns:
        Decoded token payload

    Raises:
        jwt.InvalidTokenError: If token is invalid or expired
    """
    payload: dict[str, Any] = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
    return payload
