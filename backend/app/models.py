"""SQLAlchemy Declarative Models for Healthcare Triage & EHR Platform.

Maps persistent tables: User, Case, Testimonial, ElectronicHealthRecord, SharedRecordLink, and AuditLog.
"""

import json
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional
from sqlalchemy import Column, String, Integer, Text, Boolean, DateTime, JSON, ForeignKey, func
from sqlalchemy.orm import relationship

from .database import Base

class User(Base):
    """User account credentials and clinical role authorization."""
    __tablename__ = "users"

    id = Column(String(64), primary_key=True, index=True)
    name = Column(String(128), nullable=False)
    username = Column(String(64), unique=True, nullable=False, index=True)
    email = Column(String(128), nullable=True)
    password_hash = Column(String(256), nullable=False)
    salt = Column(String(64), nullable=False)
    role = Column(String(32), nullable=False)
    status = Column(String(32), nullable=False, default="ACTIVE")
    facility = Column(String(256), nullable=True)
    created_at = Column(String(64), nullable=False)
    updated_at = Column(String(64), nullable=False)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "username": self.username,
            "email": self.email,
            "role": self.role,
            "status": self.status,
            "facility": self.facility,
            "created_at": self.created_at,
            "updated_at": self.updated_at
        }

class Case(Base):
    """Patient triage case dossiers and clinical lifecycles."""
    __tablename__ = "cases"

    id = Column(String(64), primary_key=True, index=True)
    patient_id = Column(String(64), unique=True, nullable=False, index=True)
    status = Column(String(32), nullable=False)
    priority = Column(String(32), nullable=False)
    language = Column(String(32), nullable=False)
    data = Column(JSON, nullable=False)
    created_at = Column(String(64), nullable=False)
    updated_at = Column(String(64), nullable=False)

    def to_dict(self) -> Dict[str, Any]:
        if isinstance(self.data, dict):
            res = dict(self.data)
            res["id"] = self.id
            res["patientId"] = self.patient_id
            res["status"] = self.status
            res["priority"] = self.priority
            res["language"] = self.language
            return res
        try:
            parsed = json.loads(self.data)
            parsed["id"] = self.id
            parsed["patientId"] = self.patient_id
            parsed["status"] = self.status
            parsed["priority"] = self.priority
            parsed["language"] = self.language
            return parsed
        except Exception:
            return {
                "id": self.id,
                "patientId": self.patient_id,
                "status": self.status,
                "priority": self.priority,
                "language": self.language
            }

class Testimonial(Base):
    """Patient and clinician testimonials for community health credibility."""
    __tablename__ = "testimonials"

    id = Column(String(64), primary_key=True, index=True)
    patient_name = Column(String(128), nullable=False)
    role = Column(String(64), default="Patient")
    rating = Column(Integer, nullable=False, default=5)
    comment = Column(Text, nullable=False)
    facility = Column(String(128), nullable=True)
    category = Column(String(64), default="Telecare")
    verified = Column(Boolean, default=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "patient_name": self.patient_name,
            "role": self.role,
            "rating": self.rating,
            "comment": self.comment,
            "facility": self.facility or "Rural Sub-Center",
            "category": self.category,
            "verified": self.verified,
            "created_at": self.created_at.strftime("%b %d, %Y") if self.created_at else ""
        }

class ElectronicHealthRecord(Base):
    """Longitudinal Electronic Health Record linked to patient identity."""
    __tablename__ = "electronic_health_records"

    id = Column(String(64), primary_key=True, index=True)
    patient_id = Column(String(64), nullable=False, index=True)
    vitals = Column(JSON, nullable=True, default=dict)
    prescriptions = Column(JSON, nullable=True, default=list)
    reports = Column(JSON, nullable=True, default=list)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    # Relationships
    shared_links = relationship("SharedRecordLink", back_populates="record", cascade="all, delete-orphan", lazy="joined")

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "patient_id": self.patient_id,
            "vitals": self.vitals or {},
            "prescriptions": self.prescriptions or [],
            "reports": self.reports or [],
            "created_at": self.created_at.strftime("%Y-%m-%d %I:%M %p") if self.created_at else "",
            "updated_at": self.updated_at.strftime("%Y-%m-%d %I:%M %p") if self.updated_at else ""
        }

class SharedRecordLink(Base):
    """Cryptographic temporary access token for secure EHR dossier viewing."""
    __tablename__ = "shared_record_links"

    id = Column(String(64), primary_key=True, index=True)
    record_id = Column(String(64), ForeignKey("electronic_health_records.id"), nullable=False, index=True)
    secure_token = Column(String(128), unique=True, nullable=False, index=True)
    expiry = Column(DateTime, nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    record = relationship("ElectronicHealthRecord", back_populates="shared_links")

    def is_valid(self) -> bool:
        now = datetime.now(timezone.utc)
        expiry_dt = self.expiry
        if expiry_dt.tzinfo is None:
            expiry_dt = expiry_dt.replace(tzinfo=timezone.utc)
        return now < expiry_dt

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "record_id": self.record_id,
            "secure_token": self.secure_token,
            "expiry": self.expiry.strftime("%Y-%m-%d %I:%M %p") if self.expiry else "",
            "is_valid": self.is_valid(),
            "created_at": self.created_at.strftime("%Y-%m-%d %I:%M %p") if self.created_at else ""
        }

class AuditLog(Base):
    """Immutable audit trail of clinical actions and state transitions."""
    __tablename__ = "audit_logs"

    id = Column(String(64), primary_key=True, index=True)
    case_id = Column(String(64), nullable=True, index=True)
    actor = Column(String(128), nullable=False)
    role = Column(String(64), nullable=False)
    action = Column(String(256), nullable=False)
    note = Column(Text, nullable=True)
    timestamp = Column(String(64), nullable=False)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "case_id": self.case_id,
            "actor": self.actor,
            "role": self.role,
            "action": self.action,
            "note": self.note,
            "timestamp": self.timestamp
        }
