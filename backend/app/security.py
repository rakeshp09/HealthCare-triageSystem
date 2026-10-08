"""Security, JWT Authentication, and Password Hashing Layer.

Supports PBKDF2-SHA512 password hashing with full backward compatibility
and JSON Web Token (JWT) stateless session authentication.
"""

import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from typing import Dict, Any, Optional, List
import jwt
from fastapi import Depends, HTTPException, status, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session

from .config import settings
from .database import get_db
from .models import User

http_bearer = HTTPBearer(auto_error=False)

def hash_password(password: str, salt: Optional[str] = None) -> Dict[str, str]:
    """Hashes password using PBKDF2-SHA512 (100,000 iterations)."""
    final_salt = salt or secrets.token_hex(16)
    hash_bytes = hashlib.pbkdf2_hmac(
        "sha512",
        password.encode("utf-8"),
        final_salt.encode("utf-8"),
        100000
    )
    return {"hash": hash_bytes.hex(), "salt": final_salt}

def verify_password(password: str, stored_hash: str, salt: str) -> bool:
    """Verifies candidate password against stored PBKDF2-SHA512 hash."""
    try:
        candidate_bytes = hashlib.pbkdf2_hmac(
            "sha512",
            password.encode("utf-8"),
            salt.encode("utf-8"),
            100000
        )
        return secrets.compare_digest(candidate_bytes.hex(), stored_hash)
    except Exception:
        return False

def create_access_token(data: Dict[str, Any], expires_delta: Optional[timedelta] = None) -> str:
    """Encodes JWT payload with expiration."""
    to_encode = data.copy()
    now = datetime.now(timezone.utc)
    if expires_delta:
        expire = now + expires_delta
    else:
        expire = now + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire, "iat": now})
    encoded_jwt = jwt.encode(to_encode, settings.JWT_SECRET_KEY, algorithm=settings.ALGORITHM)
    return encoded_jwt

def decode_access_token(token: str) -> Optional[Dict[str, Any]]:
    """Decodes and validates a JWT token string."""
    try:
        payload = jwt.decode(token, settings.JWT_SECRET_KEY, algorithms=[settings.ALGORITHM])
        return payload
    except Exception:
        return None

def get_current_user_optional(
    request: Request,
    token_auth: Optional[HTTPAuthorizationCredentials] = Depends(http_bearer),
    db: Session = Depends(get_db)
) -> Optional[Dict[str, Any]]:
    """Resolves authenticated user from Bearer header or cookie session (optional)."""
    token = None
    if token_auth and token_auth.credentials:
        token = token_auth.credentials
    else:
        # Check cookie
        token = request.cookies.get("access_token") or request.cookies.get("token")
        
    user_id = None
    if token:
        payload = decode_access_token(token)
        if payload:
            user_id = payload.get("sub") or payload.get("user_id")

    # If no token, check session cookie user_id
    if not user_id:
        session_user_id = request.cookies.get("user_id")
        if session_user_id:
            user_id = session_user_id

    if not user_id:
        return None

    user = db.query(User).filter(User.id == user_id).first()
    if not user or user.status.upper() != "ACTIVE":
        return None

    return user.to_dict()

def get_current_user(
    current_user: Optional[Dict[str, Any]] = Depends(get_current_user_optional)
) -> Dict[str, Any]:
    """Dependency requiring an active authenticated user."""
    if not current_user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication credentials required",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return current_user

def require_role(*allowed_roles: str):
    """Dependency factory checking user role."""
    def role_checker(user: Dict[str, Any] = Depends(get_current_user)) -> Dict[str, Any]:
        role = user.get("role", "")
        if "Admin" in role:
            return user
        matches = any(r.lower() in role.lower() for r in allowed_roles)
        if not matches:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Operation not permitted for role '{role}'"
            )
        return user
    return role_checker
