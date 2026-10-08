"""Pydantic Request and Response Schemas for Validation.
"""

from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field, ConfigDict

# -----------------
# AUTH SCHEMAS
# -----------------
class UserCreate(BaseModel):
    name: str = Field(..., min_length=2, max_length=128)
    username: str = Field(..., min_length=3, max_length=64)
    email: Optional[str] = None
    password: str = Field(..., min_length=4)
    role: str = Field(default="Patient")
    facility: Optional[str] = None

class UserLogin(BaseModel):
    username: str
    password: str

class UserResponse(BaseModel):
    id: str
    name: str
    username: str
    email: Optional[str] = None
    role: str
    status: str
    facility: Optional[str] = None
    created_at: Optional[str] = None

class TokenResponse(BaseModel):
    success: bool
    access_token: str
    token_type: str = "bearer"
    user: Dict[str, Any]

# -----------------
# CASE SCHEMAS
# -----------------
class VitalsPayload(BaseModel):
    temperature: Optional[str] = None
    spo2: Optional[str] = None
    bloodPressureSys: Optional[str] = None
    bloodPressureDia: Optional[str] = None
    heartRate: Optional[str] = None
    respiratoryRate: Optional[str] = None

class CaseCreate(BaseModel):
    patientId: Optional[str] = None
    age: Optional[Any] = None
    gender: Optional[str] = None
    language: Optional[str] = "Hindi"
    symptoms: Optional[str] = None
    symptomDuration: Optional[str] = None
    chiefConcern: Optional[str] = None
    vitals: Optional[Dict[str, Any]] = None
    medicalHistory: Optional[Dict[str, Any]] = None
    status: Optional[str] = None
    priority: Optional[str] = None
    consentObtained: Optional[bool] = True

class AdmissionApprovalPayload(BaseModel):
    model_config = ConfigDict(extra="allow")
    vitals: Optional[Dict[str, Any]] = None
    note: Optional[str] = None
    temperature: Optional[Any] = None
    temp: Optional[Any] = None
    spo2: Optional[Any] = None
    heart_rate: Optional[Any] = None
    heartRate: Optional[Any] = None
    blood_pressure: Optional[Any] = None
    bp: Optional[Any] = None
    pulse: Optional[Any] = None

class ReviewPayload(BaseModel):
    decision: str = "reviewed"
    reviewer_notes: Optional[str] = None
    reviewerNotes: Optional[str] = None
    escalation_reason: Optional[str] = None
    escalationReason: Optional[str] = None

class ReferralPayload(BaseModel):
    destinationFacility: str = "District Civil Hospital & Medical College"
    destinationDepartment: str = "Critical Care Unit"
    reason: str
    reviewerNotes: Optional[str] = ""

# -----------------
# AI & ANALYSIS SCHEMAS
# -----------------
class DietAdviceRequest(BaseModel):
    vitals: Optional[Dict[str, Any]] = None
    conditions: Optional[str] = None
    pastConditions: Optional[str] = None
    symptoms: Optional[str] = None
    age: Optional[int] = None
    language: Optional[str] = "English"

# -----------------
# RAG SCHEMAS
# -----------------
class RAGQueryRequest(BaseModel):
    query: str
    n_results: Optional[int] = 5
    collection: Optional[str] = "clinical_protocols"

class PrescriptionCreate(BaseModel):
    medication: str
    dosage: Optional[str] = ""
    frequency: Optional[str] = ""
    duration: Optional[str] = ""
    notes: Optional[str] = ""

class ShareLinkCreate(BaseModel):
    duration_hours: Optional[int] = 48
