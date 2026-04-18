"""Authentication utilities - JWT token management and password hashing."""
import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from typing import Optional

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from ..config import get_settings

security = HTTPBearer()

settings = get_settings()


def hash_password(password: str) -> str:
    """Hash password with salt using SHA-256."""
    salt = secrets.token_hex(16)
    pwd_hash = hashlib.sha256(f"{salt}{password}".encode()).hexdigest()
    return f"{salt}:{pwd_hash}"


def verify_password(password: str, password_hash: str) -> bool:
    """Verify password against stored hash."""
    salt, stored_hash = password_hash.split(":")
    pwd_hash = hashlib.sha256(f"{salt}{password}".encode()).hexdigest()
    return pwd_hash == stored_hash


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """Create JWT access token."""
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + (expires_delta or timedelta(hours=settings.JWT_EXPIRATION_HOURS))
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def decode_access_token(token: str) -> dict:
    """Decode and validate JWT token."""
    try:
        payload = jwt.decode(token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
        return payload
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token已过期")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="无效的Token")


def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)) -> dict:
    """Get current user from JWT token."""
    payload = decode_access_token(credentials.credentials)
    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="无效的Token")
    return {
        "user_id": user_id,
        "username": payload.get("username"),
        "display_name": payload.get("display_name"),
        "role": payload.get("role"),
    }


def require_roles(*roles: str):
    """Dependency to require specific roles."""
    def role_checker(current_user: dict = Depends(get_current_user)):
        if current_user["role"] not in roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="权限不足，无法执行此操作"
            )
        return current_user
    return role_checker
