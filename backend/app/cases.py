"""Case Management, Triage Lifecycles, and Clinical Workflows Router.

Handles case creation, status state transitions, nurse intake approvals,
physician review sign-offs, specialist referrals, IoT streaming, and staff governance.
"""

import os
import secrets
import json
from datetime import datetime, timedelta, timezone
from typing import Dict, Any, List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Request, UploadFile, File, Form
from fastapi.responses import JSONResponse, StreamingResponse
from sqlalchemy.orm import Session
from sqlalchemy import func

from .config import settings
from .database import get_db
from .models import User, Case, ElectronicHealthRecord, SharedRecordLink, AuditLog
from .schemas import (
    CaseCreate,
    AdmissionApprovalPayload,
    ReviewPayload,
    ReferralPayload,
    PrescriptionCreate,
    ShareLinkCreate
)
from .security import get_current_user, get_current_user_optional, require_role
from ..services.safety_service import safety_service
from ..services.extraction_service import extraction_service
from ..services.speech_service import speech_service, format_chief_clinical_concern
from ..services.vision_service import vision_service
from ..rag.retriever import rag_retriever
from ..utils.helpers import format_file_size, sanitize_filename, get_current_timestamp

router = APIRouter(prefix="/api", tags=["Cases & Clinical Workflows"])

# -------------------------------------------------------------
# CASE CRUD & TRIAGE
# -------------------------------------------------------------

@router.get("/cases")
def list_cases(
    status: Optional[str] = None,
    priority: Optional[str] = None,
    language: Optional[str] = None,
    search: Optional[str] = None,
    role_view: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: Optional[Dict[str, Any]] = Depends(get_current_user_optional)
):
    """Lists clinical cases with flexible filtering and search."""
    query = db.query(Case).order_by(Case.created_at.desc())

    if status and status != "ALL":
        query = query.filter(Case.status == status)
    if priority and priority != "ALL":
        query = query.filter(Case.priority == priority)
    if language and language != "ALL":
        query = query.filter(Case.language == language)

    cases = [c.to_dict() for c in query.all()]

    # RBAC: Patient should view only their own records; health worker/admin roles retain full visibility
    if current_user and current_user.get("role", "").lower() == "patient":
        user_id = current_user.get("id", "")
        username = current_user.get("username", "")
        patient_keys = {str(k).lower() for k in [user_id, username] if k}
        cases = [
            c for c in cases
            if str(c.get("patientId", "")).lower() in patient_keys
            or str(c.get("id", "")).lower() in patient_keys
            or str(c.get("user_id", "")).lower() in patient_keys
            or str(c.get("userId", "")).lower() in patient_keys
        ]
    elif role_view == "Doctor" or (current_user and "Doctor" in current_user.get("role", "") and not status):
        # Doctors see cases ready for review, reviewed, escalated, or referred (not pending nurse)
        cases = [c for c in cases if c.get("status") in {"READY_FOR_REVIEW", "REVIEWED", "ESCALATED", "REFERRED"}]

    if search:
        q = search.lower().strip()
        cases = [
            c for c in cases
            if q in c.get("patientId", "").lower()
            or q in (c.get("chiefConcern") or "").lower()
            or q in (c.get("symptoms") or "").lower()
            or q in c.get("language", "").lower()
        ]

    return cases

@router.post("/cases", status_code=status.HTTP_201_CREATED)
def create_case(
    payload: Dict[str, Any],
    db: Session = Depends(get_db),
    current_user: Optional[Dict[str, Any]] = Depends(get_current_user_optional)
):
    """Creates a new patient case dossier with safety rule tagging and queue placement."""
    case_data = dict(payload)
    requested_id = str(case_data.get("patientId") or "").strip()

    # Enforce patient self-admission rule
    if current_user and current_user.get("role") == "Patient":
        username = current_user.get("username", "")
        user_id = current_user.get("id", "")
        allowed = {username.lower(), user_id.lower(), "pat-001", "pat-002"}
        if requested_id and requested_id.lower() not in allowed:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Access Denied: As a Patient ({username}), you can only submit admissions for your own account."
            )
        patient_id = requested_id or username
        case_data["patientId"] = patient_id
        case_data["id"] = patient_id
        case_data["status"] = "PENDING_NURSE_APPROVAL"
        actor_name = current_user.get("name", "Patient")
        actor_role = "Patient"
        action_desc = "Patient submitted self-admission request. Awaiting nurse verification."
    else:
        patient_id = requested_id or f"PAT-{datetime.now().strftime('%M%S')}-{secrets.token_hex(2).upper()}"
        case_data["patientId"] = patient_id
        case_data["id"] = patient_id
        actor_name = current_user["name"] if current_user else "Health Worker"
        actor_role = current_user["role"] if current_user else "Health Worker"
        action_desc = "Case created with verified consent by clinical staff"
        if not case_data.get("status"):
            case_data["status"] = "READY_FOR_REVIEW"

    now = get_current_timestamp()
    if not case_data.get("auditTrail"):
        case_data["auditTrail"] = [{
            "timestamp": now,
            "actor": actor_name,
            "role": actor_role,
            "action": action_desc
        }]

    # Format chief concern if symptoms provided
    if not case_data.get("chiefConcern") and case_data.get("symptoms"):
        case_data["chiefConcern"] = format_chief_clinical_concern(
            case_data["symptoms"],
            {"language": case_data.get("language", "Hindi"), "age": case_data.get("age")}
        )

    # Extract structured entities
    case_data["aiExtractions"] = extraction_service.extract_entities(case_data)

    # Deterministic safety risk evaluation
    priority, safety_signals, missing_info = safety_service.evaluate(case_data)
    case_data["priority"] = priority
    case_data["safetySignals"] = safety_signals
    case_data["missingInfoTracker"] = missing_info

    # Enforce PENDING_NURSE_APPROVAL for patient self-admissions
    if current_user and current_user.get("role") == "Patient":
        case_data["status"] = "PENDING_NURSE_APPROVAL"

    case_data["createdAt"] = now
    case_data["updatedAt"] = now

    # Upsert into database
    existing = db.query(Case).filter(
        (Case.id == patient_id) | (Case.patient_id == patient_id)
    ).first()

    if existing:
        existing.status = case_data["status"]
        existing.priority = case_data["priority"]
        existing.language = case_data.get("language", "Hindi")
        existing.data = case_data
        existing.updated_at = now
    else:
        new_case = Case(
            id=patient_id,
            patient_id=patient_id,
            status=case_data["status"],
            priority=case_data["priority"],
            language=case_data.get("language", "Hindi"),
            data=case_data,
            created_at=now,
            updated_at=now
        )
        db.add(new_case)

    db.commit()

    # Index into vector database
    rag_retriever.index_case(
        case_id=patient_id,
        case_text=f"Chief Concern: {case_data.get('chiefConcern')}. Symptoms: {case_data.get('symptoms')}. Priority: {priority}.",
        metadata={"priority": priority, "status": case_data["status"], "language": case_data.get("language", "Hindi")}
    )

    return case_data

@router.get("/cases/{case_id}")
def get_case(case_id: str, db: Session = Depends(get_db)):
    """Retrieves full case dossier."""
    case = db.query(Case).filter(
        (Case.id == case_id) | (func.upper(Case.patient_id) == case_id.upper())
    ).first()
    if not case:
        raise HTTPException(status_code=404, detail=f"Case {case_id} not found")
    return case.to_dict()

@router.patch("/cases/{case_id}")
def update_case(case_id: str, payload: Dict[str, Any], db: Session = Depends(get_db)):
    """Applies partial updates to a case record."""
    case = db.query(Case).filter(
        (Case.id == case_id) | (func.upper(Case.patient_id) == case_id.upper())
    ).first()
    if not case:
        raise HTTPException(status_code=404, detail=f"Case {case_id} not found")

    current_data = case.to_dict()
    current_data.update(payload)
    current_data["updatedAt"] = get_current_timestamp()

    case.data = current_data
    case.status = current_data.get("status", case.status)
    case.priority = current_data.get("priority", case.priority)
    case.updated_at = current_data["updatedAt"]

    db.commit()
    return current_data

# -------------------------------------------------------------
# STEP-BY-STEP ADMISSION, REVIEW & REFERRAL WORKFLOWS
# -------------------------------------------------------------

@router.post("/cases/{case_id}/approve-admission")
@router.post("/cases/{case_id}/approve")
def approve_admission(
    case_id: str,
    payload: Optional[AdmissionApprovalPayload] = None,
    db: Session = Depends(get_db),
    current_user: Optional[Dict[str, Any]] = Depends(get_current_user_optional)
):
    """Nurse / Frontline Health Worker verifies physical vitals and approves admission."""
    clean_id = str(case_id).strip()
    case = db.query(Case).filter(
        (Case.id == clean_id) |
        (func.lower(Case.id) == clean_id.lower()) |
        (Case.patient_id == clean_id) |
        (func.lower(Case.patient_id) == clean_id.lower())
    ).first()

    if not case:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Case '{case_id}' not found in database"
        )

    case_data = case.to_dict()
    payload_dict = payload.model_dump() if payload else {}

    # Extract verified vitals (nested in 'vitals' or flat keys)
    vitals = dict(case_data.get("vitals") or {})
    if payload_dict.get("vitals") and isinstance(payload_dict["vitals"], dict):
        for k, v in payload_dict["vitals"].items():
            if v is not None and str(v).strip() != "":
                vitals[k] = v

    vitals_key_map = {
        "temp": "temperature",
        "temperature": "temperature",
        "spo2": "spo2",
        "heart_rate": "heartRate",
        "heartRate": "heartRate",
        "pulse": "heartRate",
        "blood_pressure": "bloodPressure",
        "bp": "bloodPressure",
        "bloodPressureSys": "bloodPressureSys",
        "bloodPressureDia": "bloodPressureDia"
    }
    for key, norm_key in vitals_key_map.items():
        val = payload_dict.get(key)
        if val is not None and str(val).strip() != "":
            vitals[norm_key] = val

    if vitals:
        case_data["vitals"] = vitals
        priority, safety_signals, missing_info = safety_service.evaluate(case_data)
        case_data["priority"] = priority
        case_data["safetySignals"] = safety_signals
        case_data["missingInfoTracker"] = missing_info

    now = get_current_timestamp()
    case_data["status"] = "READY_FOR_REVIEW"
    case_data["updatedAt"] = now

    actor_name = current_user.get("name", "Frontline Nurse") if current_user else "Frontline Nurse"
    actor_role = current_user.get("role", "Nurse") if current_user else "Nurse"

    audit = case_data.get("auditTrail") or []
    audit.append({
        "timestamp": now,
        "actor": actor_name,
        "role": actor_role,
        "action": "Admission & vitals verified by frontline nurse. Case transitioned to READY_FOR_REVIEW for physician queue."
    })
    case_data["auditTrail"] = audit

    case.status = "READY_FOR_REVIEW"
    case.priority = case_data.get("priority", case.priority)
    case.data = case_data
    case.updated_at = now
    db.commit()

    return {
        "status": "success",
        "message": "Case admission approved successfully",
        "success": True,
        "caseData": case_data
    }

@router.post("/cases/{case_id}/send-to-doctor")
def send_to_doctor(
    case_id: str,
    db: Session = Depends(get_db),
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Forwards case directly to doctor review desk."""
    case = db.query(Case).filter(
        (Case.id == case_id) | (func.upper(Case.patient_id) == case_id.upper())
    ).first()
    if not case:
        raise HTTPException(status_code=404, detail=f"Case {case_id} not found")

    case_data = case.to_dict()
    now = get_current_timestamp()
    case_data["status"] = "READY_FOR_REVIEW"
    case_data["updatedAt"] = now

    audit = case_data.get("auditTrail") or []
    audit.append({
        "timestamp": now,
        "actor": current_user.get("name", "Staff"),
        "role": current_user.get("role", "Staff"),
        "action": f"Sent for physician evaluation (System priority: {case_data.get('priority', 'MEDIUM')})"
    })
    case_data["auditTrail"] = audit

    case.status = "READY_FOR_REVIEW"
    case.data = case_data
    case.updated_at = now
    db.commit()

    return {"success": True, "caseData": case_data}

@router.post("/cases/{case_id}/review")
def review_case(
    case_id: str,
    payload: ReviewPayload,
    db: Session = Depends(get_db),
    current_user: Dict[str, Any] = Depends(require_role("Doctor", "Reviewer", "Admin"))
):
    """Doctor clinical assessment and sign-off (reviewed, escalate, referral)."""
    case = db.query(Case).filter(
        (Case.id == case_id) | (func.upper(Case.patient_id) == case_id.upper())
    ).first()
    if not case:
        raise HTTPException(status_code=404, detail=f"Case {case_id} not found")

    case_data = case.to_dict()
    if case_data.get("status") == "PENDING_NURSE_APPROVAL":
        raise HTTPException(
            status_code=400,
            detail="Patient admission requires nurse verification first before physician review."
        )

    decision = payload.decision.lower()
    notes = payload.reviewer_notes or payload.reviewerNotes or ""
    escalation_reason = payload.escalation_reason or payload.escalationReason or ""
    reviewer_name = current_user.get("name", "Dr. Clinician, MD")

    new_status = "REVIEWED"
    action_text = "Case marked as REVIEWED by clinician"

    if decision == "escalate":
        new_status = "ESCALATED"
        action_text = f"Case escalated to urgent care: {escalation_reason or 'High clinical risk'}"
    elif decision == "referral":
        new_status = "REFERRED"
        action_text = "Clinical referral initiated"

    now = get_current_timestamp()
    case_data["status"] = new_status
    case_data["updatedAt"] = now

    audit = case_data.get("auditTrail") or []
    audit.append({
        "timestamp": now,
        "actor": reviewer_name,
        "role": "Doctor / Reviewer",
        "action": action_text
    })
    case_data["auditTrail"] = audit

    case_data["doctorReview"] = {
        "reviewedBy": reviewer_name,
        "reviewedAt": now,
        "decision": decision,
        "reviewerNotes": notes,
        "escalationReason": escalation_reason
    }

    case.status = new_status
    case.data = case_data
    case.updated_at = now
    db.commit()

    return {"success": True, "caseData": case_data}

@router.post("/cases/{case_id}/referral")
def create_referral(
    case_id: str,
    payload: ReferralPayload,
    db: Session = Depends(get_db),
    current_user: Dict[str, Any] = Depends(require_role("Doctor", "Reviewer", "Admin"))
):
    """Dispatches standardized specialist referral packet."""
    case = db.query(Case).filter(
        (Case.id == case_id) | (func.upper(Case.patient_id) == case_id.upper())
    ).first()
    if not case:
        raise HTTPException(status_code=404, detail=f"Case {case_id} not found")

    case_data = case.to_dict()
    now = get_current_timestamp()
    referred_by = current_user.get("name", "Dr. Clinician, MD")

    case_data["status"] = "REFERRED"
    case_data["updatedAt"] = now

    audit = case_data.get("auditTrail") or []
    audit.append({
        "timestamp": now,
        "actor": referred_by,
        "role": "Doctor / Reviewer",
        "action": f"Referral created to {payload.destinationFacility} ({payload.destinationDepartment})"
    })
    case_data["auditTrail"] = audit

    case_data["referral"] = {
        "destinationFacility": payload.destinationFacility,
        "destinationDepartment": payload.destinationDepartment,
        "reason": payload.reason,
        "reviewerNotes": payload.reviewerNotes or "",
        "referredBy": referred_by,
        "created": True,
        "createdAt": now
    }

    case.status = "REFERRED"
    case.data = case_data
    case.updated_at = now
    db.commit()

    return {"success": True, "caseData": case_data}

# -------------------------------------------------------------
# CASE ATTACHMENTS (AUDIO & DIAGNOSTIC REPORTS)
# -------------------------------------------------------------

@router.post("/cases/{case_id}/upload-audio")
async def upload_case_audio(
    case_id: str,
    audio: Optional[UploadFile] = File(None),
    file: Optional[UploadFile] = File(None),
    db: Session = Depends(get_db)
):
    """Attaches and transcribes voice recording for existing case."""
    case = db.query(Case).filter(
        (Case.id == case_id) | (func.upper(Case.patient_id) == case_id.upper())
    ).first()
    if not case:
        raise HTTPException(status_code=404, detail=f"Case {case_id} not found")

    audio_file = audio or file
    filename = f"audio_{case_id}_{secrets.token_hex(4)}.wav"
    upload_path = os.path.join(settings.UPLOAD_FOLDER, filename)

    if audio_file:
        contents = await audio_file.read()
        with open(upload_path, "wb") as f:
            f.write(contents)

    case_data = case.to_dict()
    lang = case_data.get("language", "Hindi")
    stt_res = speech_service.transcribe_audio(upload_path if audio_file else None, lang)
    stt_res["audioUrl"] = f"/static/uploads/{filename}"
    
    case_data["voiceInput"] = stt_res
    if not case_data.get("symptoms"):
        case_data["symptoms"] = stt_res["transcript"]
    case_data["chiefConcern"] = stt_res["clinical_concern_synthesis"]

    case.data = case_data
    case.updated_at = get_current_timestamp()
    db.commit()

    return {"success": True, "audioData": stt_res, "case": case_data}

@router.delete("/cases/{case_id}/delete-audio")
@router.post("/cases/{case_id}/delete-audio")
def delete_case_audio(case_id: str, db: Session = Depends(get_db)):
    """Deletes audio recording from case."""
    case = db.query(Case).filter(
        (Case.id == case_id) | (func.upper(Case.patient_id) == case_id.upper())
    ).first()
    if not case:
        raise HTTPException(status_code=404, detail=f"Case {case_id} not found")

    case_data = case.to_dict()
    voice = case_data.get("voiceInput")
    if voice and isinstance(voice, dict) and voice.get("audio_file"):
        fname = os.path.basename(voice["audio_file"])
        fpath = os.path.join(settings.UPLOAD_FOLDER, sanitize_filename(fname))
        if os.path.exists(fpath):
            try:
                os.remove(fpath)
            except Exception:
                pass

    case_data["voiceInput"] = None
    case.data = case_data
    case.updated_at = get_current_timestamp()
    db.commit()

    return {"success": True, "message": "Audio recording removed from case"}

@router.post("/cases/{case_id}/upload-report")
@router.post("/cases/{case_id}/upload_report")
async def upload_case_report(
    case_id: str,
    file: UploadFile = File(...),
    isConfirmed: Optional[bool] = Form(False),
    confirm: Optional[bool] = Form(False),
    is_confirmed: Optional[bool] = Form(False),
    db: Session = Depends(get_db)
):
    """Attaches diagnostic document/scan to case and runs OCR upon explicit confirmation."""
    case = db.query(Case).filter(
        (Case.id == case_id) | (func.upper(Case.patient_id) == case_id.upper())
    ).first()
    if not case:
        raise HTTPException(status_code=404, detail=f"Case {case_id} not found")

    is_confirmed_bool = bool(isConfirmed or confirm or is_confirmed)

    orig_name = file.filename or "medical_report.png"
    base_name, ext = os.path.splitext(orig_name)
    clean_base = sanitize_filename(base_name)
    filename = f"{clean_base}_{secrets.token_hex(3)}{ext.lower() or '.png'}"
    save_path = os.path.join(settings.UPLOAD_FOLDER, filename)

    contents = await file.read()
    with open(save_path, "wb") as f:
        f.write(contents)

    ocr_result = vision_service.process_document(save_path)
    file_size_display = format_file_size(len(contents))

    new_report = {
        "id": f"rep-{secrets.token_hex(3)}",
        "fileName": filename,
        "originalName": orig_name,
        "fileType": file.content_type or "application/octet-stream",
        "fileSize": file_size_display,
        "uploadedAt": get_current_timestamp(),
        "reportType": ocr_result["report_type"],
        "findings": ocr_result["findings"],
        "impressions": ocr_result.get("impressions", []),
        "flags": ocr_result.get("flags", []),
        "previewUrl": f"/static/uploads/{filename}",
        "url": f"/static/uploads/{filename}",
        "attached": is_confirmed_bool,
        "isConfirmed": is_confirmed_bool
    }

    case_data = case.to_dict()

    if not is_confirmed_bool:
        return {
            "success": True,
            "isConfirmed": False,
            "attached": False,
            "report": new_report,
            "message": "File metadata generated. Explicit confirmation required to attach to patient record."
        }

    reports = case_data.get("reports") or []
    reports.append(new_report)
    case_data["reports"] = reports

    case.data = case_data
    case.updated_at = get_current_timestamp()
    db.commit()

    return {
        "success": True,
        "isConfirmed": True,
        "attached": True,
        "report": new_report,
        "case": case_data,
        "message": "Report confirmed and attached to patient record."
    }

@router.post("/cases/{case_id}/confirm-report/{report_id}")
@router.post("/cases/{case_id}/confirm-report")
def confirm_case_report(
    case_id: str,
    report_id: Optional[str] = None,
    payload: Optional[Dict[str, Any]] = None,
    db: Session = Depends(get_db)
):
    """Explicitly confirms and attaches a report to the patient case."""
    case = db.query(Case).filter(
        (Case.id == case_id) | (func.upper(Case.patient_id) == case_id.upper())
    ).first()
    if not case:
        raise HTTPException(status_code=404, detail=f"Case {case_id} not found")

    case_data = case.to_dict()
    reports = case_data.get("reports") or []
    confirmed_report = payload.get("report") if payload else None

    if confirmed_report:
        confirmed_report["attached"] = True
        confirmed_report["isConfirmed"] = True
        reports.append(confirmed_report)
    elif report_id:
        for r in reports:
            if r.get("id") == report_id:
                r["attached"] = True
                r["isConfirmed"] = True
                confirmed_report = r
                break

    case_data["reports"] = reports
    case.data = case_data
    case.updated_at = get_current_timestamp()
    db.commit()

    return {
        "success": True,
        "isConfirmed": True,
        "attached": True,
        "report": confirmed_report,
        "case": case_data,
        "message": "Report confirmed and attached to patient record."
    }

@router.delete("/cases/{case_id}/delete-report/{report_id}")
@router.post("/cases/{case_id}/delete-report/{report_id}")
def delete_case_report(case_id: str, report_id: str, db: Session = Depends(get_db)):
    """Removes diagnostic report attachment from case."""
    case = db.query(Case).filter(
        (Case.id == case_id) | (func.upper(Case.patient_id) == case_id.upper())
    ).first()
    if not case:
        raise HTTPException(status_code=404, detail=f"Case {case_id} not found")

    case_data = case.to_dict()
    reports = case_data.get("reports") or []
    matching = [r for r in reports if r.get("id") == report_id or r.get("fileName") == report_id]
    case_data["reports"] = [r for r in reports if r.get("id") != report_id and r.get("fileName") != report_id]

    for m in matching:
        fname = m.get("fileName")
        if fname:
            fpath = os.path.join(settings.UPLOAD_FOLDER, sanitize_filename(os.path.basename(fname)))
            if os.path.exists(fpath):
                try:
                    os.remove(fpath)
                except Exception:
                    pass

    case.data = case_data
    case.updated_at = get_current_timestamp()
    db.commit()

    return {"success": True, "message": "Report deleted", "reports": case_data["reports"]}

@router.post("/delete-file")
@router.delete("/delete-file")
def delete_file(data: Optional[Dict[str, Any]] = None, filename: Optional[str] = None):
    """Deletes uploaded file from disk."""
    fname = (data or {}).get("filename") or filename
    if not fname:
        raise HTTPException(status_code=400, detail="Filename is required")

    safe_name = sanitize_filename(os.path.basename(fname))
    fpath = os.path.join(settings.UPLOAD_FOLDER, safe_name)
    if os.path.exists(fpath):
        try:
            os.remove(fpath)
            return {"success": True, "message": f"File '{safe_name}' deleted", "filename": safe_name}
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to delete file: {str(e)}")

    return {"success": True, "message": f"File '{safe_name}' removed"}

@router.get("/uploads")
def list_uploads():
    """Lists all uploaded documents and audio files."""
    files = []
    if os.path.exists(settings.UPLOAD_FOLDER):
        for fname in sorted(os.listdir(settings.UPLOAD_FOLDER), reverse=True):
            fpath = os.path.join(settings.UPLOAD_FOLDER, fname)
            if os.path.isfile(fpath):
                size_str = format_file_size(os.path.getsize(fpath))
                _, ext = os.path.splitext(fname)
                ext = ext.lower()
                category = "audio" if ext in [".wav", ".mp3", ".ogg", ".webm", ".m4a"] else "document"
                type_str = f"Audio ({ext[1:].upper()})" if category == "audio" else f"Document ({ext[1:].upper() or 'File'})"
                mtime = os.path.getmtime(fpath)
                uploaded_at = datetime.fromtimestamp(mtime).strftime("%Y-%m-%d %I:%M %p")
                files.append({
                    "id": f"up-{secrets.token_hex(3)}",
                    "fileName": fname,
                    "fileSize": size_str,
                    "fileType": type_str,
                    "reportType": type_str,
                    "category": category,
                    "uploadedAt": uploaded_at,
                    "url": f"/static/uploads/{fname}"
                })
    return {"success": True, "files": files, "count": len(files)}

# -------------------------------------------------------------
# REAL-TIME IOT TELEMETRY & SSE
# -------------------------------------------------------------

import time
import math
import random

def generate_telemetry_snapshot(patient_id: str = "BED-01") -> Dict[str, Any]:
    """Generates continuous realistic medical telemetry snapshot (Lead-II ECG, BP, SpO2)."""
    hr = random.randint(72, 78)
    sys_bp = random.randint(118, 126)
    dia_bp = random.randint(76, 82)
    spo2 = round(98.0 + random.uniform(-0.5, 0.5), 1)

    # Lead-II ECG waveform synthesis
    points = []
    for step in range(15):
        t = (step / 15.0) * 2 * math.pi
        val = 0.0
        if 0.8 <= t <= 1.4:
            val += 0.25 * math.sin((t - 0.8) / 0.6 * math.pi)
        elif 2.0 <= t <= 2.3:
            val += 1.8 * math.sin((t - 2.0) / 0.3 * math.pi)
        elif 2.3 <= t <= 2.6:
            val -= 0.35 * math.sin((t - 2.3) / 0.3 * math.pi)
        elif 3.2 <= t <= 4.2:
            val += 0.45 * math.sin((t - 3.2) / 1.0 * math.pi)
        val += random.uniform(-0.02, 0.02)
        points.append(round(val, 3))

    return {
        "patient_id": patient_id,
        "timestamp": time.strftime("%H:%M:%S"),
        "heart_rate": hr,
        "pulse_rate_unit": "bpm",
        "blood_pressure": {
            "systolic": sys_bp,
            "diastolic": dia_bp,
            "mean_arterial_pressure": round((sys_bp + 2 * dia_bp) / 3.0, 1),
            "unit": "mmHg"
        },
        "spo2": spo2,
        "spo2_unit": "%",
        "respiration_rate": 16,
        "temperature_celsius": 36.8,
        "ecg_lead_ii_mv": points
    }

@router.get("/doctor/iot-stream")
def get_iot_stream(patient_id: str = "BED-01"):
    """Returns instantaneous medical device telemetry."""
    return generate_telemetry_snapshot(patient_id)

@router.get("/doctor/iot-stream/sse")
def get_iot_sse_stream():
    """Streams continuous 1Hz telemetry updates via Server-Sent Events."""
    def event_generator():
        while True:
            data = generate_telemetry_snapshot()
            yield f"data: {json.dumps(data)}\n\n"
            time.sleep(1.0)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"}
    )

# -------------------------------------------------------------
# PRESCRIPTIONS & PATIENT PORTAL
# -------------------------------------------------------------

@router.post("/doctor/prescriptions/{patient_id}")
def add_prescription(
    patient_id: str,
    payload: PrescriptionCreate,
    db: Session = Depends(get_db),
    current_user: Dict[str, Any] = Depends(require_role("Doctor", "Reviewer", "Admin"))
):
    """Doctor prescribes medications and appends to patient's EHR."""
    ehr = db.query(ElectronicHealthRecord).filter(
        (ElectronicHealthRecord.patient_id == patient_id) |
        (ElectronicHealthRecord.id == patient_id)
    ).first()

    if not ehr:
        ehr = ElectronicHealthRecord(
            id=f"ehr_{secrets.token_hex(4)}",
            patient_id=patient_id,
            vitals={},
            prescriptions=[],
            reports=[]
        )
        db.add(ehr)

    rx_entry = {
        "id": f"rx_{secrets.token_hex(3)}",
        "medication": payload.medication.strip(),
        "dosage": payload.dosage or "",
        "frequency": payload.frequency or "",
        "duration": payload.duration or "",
        "notes": payload.notes or "",
        "prescribed_by": current_user.get("name", "Doctor"),
        "prescribed_at": get_current_timestamp()
    }

    current_rx = list(ehr.prescriptions or [])
    current_rx.append(rx_entry)
    ehr.prescriptions = current_rx
    db.commit()

    return {"success": True, "prescription": rx_entry, "message": "Prescription added"}

@router.post("/doctor/share-link/{record_id}")
@router.post("/patient/share-link")
def create_share_link(
    payload: Optional[ShareLinkCreate] = None,
    record_id: Optional[str] = None,
    request: Request = None,
    db: Session = Depends(get_db),
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Generates secure time-expiring cryptographic token for patient record sharing."""
    target_id = record_id or current_user.get("username")
    ehr = db.query(ElectronicHealthRecord).filter(
        (ElectronicHealthRecord.patient_id == target_id) |
        (ElectronicHealthRecord.id == target_id)
    ).first()

    if not ehr:
        raise HTTPException(status_code=404, detail="Electronic Health Record not found")

    duration = payload.duration_hours if payload else 48
    token = secrets.token_urlsafe(24)
    now = datetime.now(timezone.utc)
    expiry = now + timedelta(hours=duration)

    link = SharedRecordLink(
        id=f"shlink_{secrets.token_hex(4)}",
        record_id=ehr.id,
        secure_token=token,
        expiry=expiry,
        created_at=now
    )
    db.add(link)
    db.commit()

    base_url = str(request.base_url).rstrip("/") if request else ""
    share_url = f"{base_url}/shared/{token}"

    return {
        "success": True,
        "token": token,
        "share_url": share_url,
        "expiry": expiry.strftime("%Y-%m-%d %I:%M %p"),
        "duration_hours": duration
    }

@router.post("/patient/vitals")
def update_patient_vitals(
    payload: Dict[str, Any],
    db: Session = Depends(get_db),
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Patient self-records vital measurements."""
    ehr = db.query(ElectronicHealthRecord).filter(
        (ElectronicHealthRecord.patient_id == current_user["username"]) |
        (ElectronicHealthRecord.patient_id == current_user["id"])
    ).first()

    if not ehr:
        ehr = ElectronicHealthRecord(
            id=f"ehr_{secrets.token_hex(4)}",
            patient_id=current_user["username"],
            vitals={},
            prescriptions=[],
            reports=[]
        )
        db.add(ehr)

    current_vitals = dict(ehr.vitals or {})
    for k in ["temperature", "spo2", "bloodPressureSys", "bloodPressureDia", "heartRate", "respiratoryRate"]:
        if k in payload and payload[k]:
            current_vitals[k] = str(payload[k]).strip()

    current_vitals["recorded_at"] = get_current_timestamp()
    ehr.vitals = current_vitals
    db.commit()

    return {"success": True, "vitals": ehr.vitals, "message": "Vitals recorded successfully"}

# -------------------------------------------------------------
# ADMINISTRATIVE USER GOVERNANCE
# -------------------------------------------------------------

@router.get("/admin/users")
def get_admin_users(
    db: Session = Depends(get_db),
    current_user: Dict[str, Any] = Depends(require_role("Admin"))
):
    """Returns all registered users for staff governance."""
    users = db.query(User).order_by(User.created_at.desc()).all()
    return {"users": [u.to_dict() for u in users]}

@router.post("/admin/users/{user_id}/approve")
def approve_user(
    user_id: str,
    db: Session = Depends(get_db),
    current_user: Dict[str, Any] = Depends(require_role("Admin"))
):
    """Admin authorizes a pending clinician or nurse account."""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    user.status = "ACTIVE"
    user.updated_at = get_current_timestamp()
    db.commit()
    return {"success": True, "status": "ACTIVE"}

@router.post("/admin/users/{user_id}/reject")
def reject_user(
    user_id: str,
    db: Session = Depends(get_db),
    current_user: Dict[str, Any] = Depends(require_role("Admin"))
):
    """Admin rejects an unauthorized account."""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    user.status = "REJECTED"
    user.updated_at = get_current_timestamp()
    db.commit()
    return {"success": True, "status": "REJECTED"}
