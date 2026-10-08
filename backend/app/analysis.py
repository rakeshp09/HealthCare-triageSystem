"""Multimodal AI Case Analysis and Diagnostic Processing Router.

Handles speech-to-text audio processing, document OCR vision analysis,
end-to-end clinical case analysis, and personalized nutrition consultations.
"""

import os
import secrets
from typing import Dict, Any, Optional
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, Request
from sqlalchemy.orm import Session

from .config import settings
from .database import get_db
from .models import Case
from .schemas import DietAdviceRequest
from ..services.speech_service import speech_service
from ..services.vision_service import vision_service
from ..services.extraction_service import extraction_service
from ..services.safety_service import safety_service
from ..services.language_service import language_service
from ..services.rag_service import rag_service
from ..utils.helpers import format_file_size, sanitize_filename, get_current_timestamp

router = APIRouter(prefix="/api", tags=["Multimodal AI Analysis"])

@router.post("/process-audio")
async def process_audio(
    audio: Optional[UploadFile] = File(None),
    file: Optional[UploadFile] = File(None),
    language: Optional[str] = Form("Hindi")
):
    """Processes uploaded or recorded audio files via Whisper speech service."""
    audio_file = audio or file
    if not audio_file:
        raise HTTPException(status_code=400, detail="No audio file provided")

    orig_name = audio_file.filename or "intake_voice.wav"
    base_name, ext = os.path.splitext(orig_name)
    ext = ext.lower()
    if ext not in [".wav", ".mp3", ".ogg", ".webm", ".m4a"]:
        ext = ".wav"

    clean_base = sanitize_filename(base_name)
    filename = f"{clean_base}_{secrets.token_hex(3)}{ext}"
    save_path = os.path.join(settings.UPLOAD_FOLDER, filename)

    contents = await audio_file.read()
    with open(save_path, "wb") as f:
        f.write(contents)

    stt_result = speech_service.transcribe_audio(audio_path=save_path, language=language or "Hindi")
    stt_result["audioUrl"] = f"/static/uploads/{filename}"
    file_size_display = format_file_size(len(contents))

    return {
        "success": True,
        "filename": filename,
        "originalName": orig_name,
        "fileSize": file_size_display,
        "fileType": f"Audio ({ext[1:].upper()})",
        "transcript": stt_result["transcript"],
        "clinical_concern_synthesis": stt_result["clinical_concern_synthesis"],
        "detected_language": stt_result["detected_language"],
        "duration": stt_result["duration"],
        "audioUrl": stt_result["audioUrl"],
        "audioData": stt_result
    }

@router.post("/process-document")
@router.post("/upload-document")
async def process_document(
    file: Optional[UploadFile] = File(None),
    document: Optional[UploadFile] = File(None),
    report: Optional[UploadFile] = File(None),
    reportFile: Optional[UploadFile] = File(None),
    isConfirmed: Optional[bool] = Form(False),
    confirm: Optional[bool] = Form(False),
    is_confirmed: Optional[bool] = Form(False)
):
    """Processes uploaded medical reports (PDF, JPG, PNG) via OCR vision service."""
    doc_file = file or document or report or reportFile
    if not doc_file:
        raise HTTPException(status_code=400, detail="No document file provided")

    is_confirmed_bool = bool(isConfirmed or confirm or is_confirmed)

    orig_name = doc_file.filename or "medical_report.png"
    base_name, ext = os.path.splitext(orig_name)
    ext = ext.lower()
    if ext not in [".png", ".jpg", ".jpeg", ".pdf", ".webp", ".txt"]:
        ext = ".png"

    clean_base = sanitize_filename(base_name)
    filename = f"{clean_base}_{secrets.token_hex(3)}{ext}"
    save_path = os.path.join(settings.UPLOAD_FOLDER, filename)

    contents = await doc_file.read()
    with open(save_path, "wb") as f:
        f.write(contents)

    ocr_result = vision_service.process_document(save_path)
    file_size_display = format_file_size(len(contents))

    report_data = {
        "id": f"rep-{secrets.token_hex(3)}",
        "fileName": filename,
        "originalName": orig_name,
        "fileType": ocr_result["report_type"],
        "fileSize": file_size_display,
        "uploadedAt": get_current_timestamp(),
        "reportType": ocr_result["report_type"],
        "findings": ocr_result["findings"],
        "impressions": ocr_result.get("impressions", []),
        "flags": ocr_result.get("flags", []),
        "ocrConfidence": ocr_result.get("ocr_confidence", 0.94),
        "url": f"/static/uploads/{filename}",
        "previewUrl": f"/static/uploads/{filename}",
        "attached": is_confirmed_bool,
        "isConfirmed": is_confirmed_bool
    }

    return {
        "success": True,
        "isConfirmed": is_confirmed_bool,
        "attached": is_confirmed_bool,
        "report": report_data,
        "filename": filename,
        "originalName": orig_name,
        "fileSize": file_size_display,
        "fileType": ocr_result["report_type"],
        "reportUrl": report_data["url"],
        "message": "Report confirmed and attached." if is_confirmed_bool else "File metadata generated. Awaiting confirmation before attaching."
    }

@router.post("/upload_report")
@router.post("/upload-report")
async def upload_report(
    file: Optional[UploadFile] = File(None),
    document: Optional[UploadFile] = File(None),
    report: Optional[UploadFile] = File(None),
    reportFile: Optional[UploadFile] = File(None),
    case_id: Optional[str] = Form(None),
    patient_id: Optional[str] = Form(None),
    isConfirmed: Optional[bool] = Form(False),
    confirm: Optional[bool] = Form(False),
    is_confirmed: Optional[bool] = Form(False),
    db: Session = Depends(get_db)
):
    """Uploads medical report, extracts OCR metadata, and attaches only upon explicit confirmation."""
    doc_file = file or document or report or reportFile
    if not doc_file:
        raise HTTPException(status_code=400, detail="No document file provided")

    is_confirmed_bool = bool(isConfirmed or confirm or is_confirmed)

    orig_name = doc_file.filename or "medical_report.pdf"
    base_name, ext = os.path.splitext(orig_name)
    ext = ext.lower()
    if ext not in [".png", ".jpg", ".jpeg", ".pdf", ".webp", ".txt"]:
        ext = ".pdf"

    clean_base = sanitize_filename(base_name)
    filename = f"{clean_base}_{secrets.token_hex(3)}{ext}"
    save_path = os.path.join(settings.UPLOAD_FOLDER, filename)

    contents = await doc_file.read()
    with open(save_path, "wb") as f:
        f.write(contents)

    ocr_result = vision_service.process_document(save_path)
    file_size_display = format_file_size(len(contents))

    report_data = {
        "id": f"rep-{secrets.token_hex(3)}",
        "fileName": filename,
        "originalName": orig_name,
        "fileType": ocr_result["report_type"],
        "fileSize": file_size_display,
        "uploadedAt": get_current_timestamp(),
        "reportType": ocr_result["report_type"],
        "findings": ocr_result["findings"],
        "impressions": ocr_result.get("impressions", []),
        "flags": ocr_result.get("flags", []),
        "ocrConfidence": ocr_result.get("ocr_confidence", 0.94),
        "url": f"/static/uploads/{filename}",
        "previewUrl": f"/static/uploads/{filename}",
        "attached": is_confirmed_bool,
        "isConfirmed": is_confirmed_bool
    }

    # Only save to patient record in DB when explicit confirmation is given
    target_id = case_id or patient_id
    if target_id and is_confirmed_bool:
        case = db.query(Case).filter(
            (Case.id == target_id) | (Case.patient_id == target_id)
        ).first()
        if case:
            case_data = case.to_dict()
            reports = case_data.get("reports") or []
            reports.append(report_data)
            case_data["reports"] = reports
            case.data = case_data
            case.updated_at = get_current_timestamp()
            db.commit()

    return {
        "success": True,
        "isConfirmed": is_confirmed_bool,
        "attached": is_confirmed_bool,
        "report": report_data,
        "filename": filename,
        "originalName": orig_name,
        "fileSize": file_size_display,
        "fileType": ocr_result["report_type"],
        "reportUrl": report_data["url"],
        "message": (
            "Report confirmed and attached to patient record."
            if is_confirmed_bool
            else "File metadata generated. Explicit confirmation required to attach to patient record."
        )
    }

@router.post("/cases/{case_id}/analyze")
def analyze_case(case_id: str, payload: Optional[Dict[str, Any]] = None, db: Session = Depends(get_db)):
    """Runs complete multimodal intake analysis and AI entity extraction on a case."""
    case = db.query(Case).filter(
        (Case.id == case_id) | (Case.patient_id == case_id)
    ).first()
    if not case:
        raise HTTPException(status_code=404, detail=f"Case {case_id} not found")

    case_data = case.to_dict()
    if payload:
        case_data.update(payload)

    # Entity extraction
    case_data["aiExtractions"] = extraction_service.extract_entities(case_data)

    # Safety rules & priority evaluation
    priority, safety_signals, missing_info = safety_service.evaluate(case_data)
    case_data["priority"] = priority
    case_data["safetySignals"] = safety_signals
    case_data["missingInfoTracker"] = missing_info
    case_data["updatedAt"] = get_current_timestamp()

    case.data = case_data
    case.priority = priority
    case.updated_at = case_data["updatedAt"]
    db.commit()

    return {"result": case_data.get("aiExtractions"), "case": case_data}

@router.post("/patient/diet-advice")
def get_diet_advice(payload: DietAdviceRequest):
    """Returns AI-guided personalized clinical dietary advice."""
    advice = language_service.generate_diet_advice(
        vitals=payload.vitals,
        conditions=payload.conditions or payload.pastConditions,
        symptoms=payload.symptoms,
        age=payload.age,
        language=payload.language or "English"
    )
    return {"success": True, "diet_plan": advice, "nutrition_plan": advice}

@router.post("/extract_entities")
@router.get("/extract_entities")
async def extract_entities(
    request: Request,
    payload: Optional[Dict[str, Any]] = None,
    file: Optional[UploadFile] = File(None),
    report: Optional[UploadFile] = File(None)
):
    """Auto-extracts available clinical values from text or reports, checks against required schema, and identifies missing fields."""
    body_data = {}
    try:
        raw_body = await request.body()
        if raw_body:
            import json
            try:
                body_data = json.loads(raw_body.decode("utf-8"))
            except Exception:
                pass
    except Exception:
        pass

    if payload:
        body_data.update(payload)

    # If file was provided, parse with vision OCR
    doc_file = file or report
    report_data = body_data.get("report")
    text = body_data.get("text") or body_data.get("findings") or body_data.get("narrative") or ""

    if doc_file:
        orig_name = doc_file.filename or "medical_report.png"
        base_name, ext = os.path.splitext(orig_name)
        clean_base = sanitize_filename(base_name)
        fname = f"{clean_base}_{secrets.token_hex(3)}{ext.lower() or '.png'}"
        save_path = os.path.join(settings.UPLOAD_FOLDER, fname)
        contents = await doc_file.read()
        with open(save_path, "wb") as f:
            f.write(contents)
        ocr_result = vision_service.process_document(save_path)
        report_data = {
            "id": f"rep-{secrets.token_hex(3)}",
            "fileName": fname,
            "originalName": orig_name,
            "reportType": ocr_result["report_type"],
            "findings": ocr_result["findings"],
            "impressions": ocr_result.get("impressions", []),
            "flags": ocr_result.get("flags", []),
            "ocrConfidence": ocr_result.get("ocr_confidence", 0.94),
            "url": f"/static/uploads/{fname}"
        }
        if not text:
            text = f"{ocr_result['findings']} {' '.join(ocr_result.get('impressions', []))}"

    existing_case = body_data.get("case_data") or body_data.get("existing_data") or {}

    result = rag_service.extract_entities_and_check_schema(
        text=text,
        report_data=report_data,
        existing_data=existing_case
    )

    if report_data and "report" not in result:
        result["report"] = report_data

    return result
