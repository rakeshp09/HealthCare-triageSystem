"""Authentication API Router.

Handles login, account registration, session logout, and profile queries.
"""

import secrets
from datetime import datetime, timezone
from typing import Dict, Any
from fastapi import APIRouter, Depends, HTTPException, status, Response, Request
from sqlalchemy.orm import Session

from .database import get_db
from .models import User, ElectronicHealthRecord
from .schemas import UserCreate, UserLogin, TokenResponse
from .security import (
    hash_password,
    verify_password,
    create_access_token,
    get_current_user,
    get_current_user_optional
)

router = APIRouter(prefix="/api/auth", tags=["Authentication"])

@router.post("/login")
def login(payload: UserLogin, response: Response, db: Session = Depends(get_db)):
    """Authenticates credentials, generates JWT token, and sets secure auth cookie."""
    username = payload.username.strip().lower()
    user = db.query(User).filter(db.func.lower(User.username) == username).first()

    if not user or not verify_password(payload.password.strip(), user.password_hash, user.salt):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password"
        )

    if user.status.upper() == "PENDING":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Your staff account is awaiting administrative approval."
        )

    if user.status.upper() == "REJECTED":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Your account has been rejected. Please contact the clinical administrator."
        )

    token = create_access_token(data={"sub": user.id, "username": user.username, "role": user.role})
    
    # Set cookies for web frontend session compatibility
    response.set_cookie(key="access_token", value=token, httponly=True, samesite="lax", max_age=86400)
    response.set_cookie(key="user_id", value=user.id, httponly=True, samesite="lax", max_age=86400)
    response.set_cookie(key="token", value=token, samesite="lax", max_age=86400)

    return {
        "success": True,
        "message": "Login successful",
        "access_token": token,
        "token_type": "bearer",
        "user": user.to_dict()
    }

@router.post("/signup", status_code=status.HTTP_201_CREATED)
def signup(payload: UserCreate, response: Response, db: Session = Depends(get_db)):
    """Registers a new user account with role-specific onboarding."""
    clean_username = payload.username.strip().lower()
    existing = db.query(User).filter(db.func.lower(User.username) == clean_username).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Username '{payload.username}' is already taken."
        )

    creds = hash_password(payload.password)
    user_id = f"usr_{secrets.token_hex(6)}"
    now = datetime.now().strftime("%Y-%m-%d %I:%M %p")

    # Patients auto-active; clinicians require admin approval
    is_patient = payload.role.strip().lower() == "patient"
    user_status = "ACTIVE" if is_patient else "PENDING"

    new_user = User(
        id=user_id,
        name=payload.name.strip(),
        username=clean_username,
        email=payload.email.strip() if payload.email else None,
        password_hash=creds["hash"],
        salt=creds["salt"],
        role=payload.role.strip(),
        status=user_status,
        facility=payload.facility.strip() if payload.facility else None,
        created_at=now,
        updated_at=now
    )
    db.session.add(new_user) if hasattr(db, "session") else db.add(new_user)
    db.commit()
    db.refresh(new_user)

    # Initialize patient EHR container if patient role
    if is_patient:
        ehr_id = f"ehr_{secrets.token_hex(4)}"
        ehr = ElectronicHealthRecord(
            id=ehr_id,
            patient_id=new_user.username,
            vitals={},
            prescriptions=[],
            reports=[]
        )
        db.add(ehr)
        db.commit()

    token = create_access_token(data={"sub": new_user.id, "username": new_user.username, "role": new_user.role})
    response.set_cookie(key="access_token", value=token, httponly=True, samesite="lax", max_age=86400)
    response.set_cookie(key="user_id", value=new_user.id, httponly=True, samesite="lax", max_age=86400)

    return {
        "success": True,
        "user": new_user.to_dict(),
        "access_token": token,
        "message": "Account created successfully" if user_status == "ACTIVE" else "Account created successfully. Awaiting administrator approval."
    }

@router.get("/me")
def get_profile(current_user: Dict[str, Any] = Depends(get_current_user)):
    """Returns currently authenticated user profile."""
    return {"authenticated": True, "user": current_user}

@router.post("/logout")
@router.get("/logout")
def logout(response: Response):
    """Clears authentication session cookies."""
    response.delete_cookie(key="access_token", path="/")
    response.delete_cookie(key="user_id", path="/")
    response.delete_cookie(key="token", path="/")
    return {"success": True, "message": "Logged out successfully"}
