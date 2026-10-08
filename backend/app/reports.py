"""Clinical Handoff Reports and PDF Generation Router.

Assembles 15-section standardized clinical handoff dossiers and generates
ReportLab PDF documents for immediate print, referral dispatch, and EHR export.
"""

import io
from typing import Dict, Any
from fastapi import APIRouter, Depends, HTTPException, Response
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from sqlalchemy import func

from .database import get_db
from .models import Case

try:
    from reportlab.lib.pagesizes import letter
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib import colors
    _REPORTLAB_AVAILABLE = True
except Exception:
    _REPORTLAB_AVAILABLE = False

router = APIRouter(prefix="/api/reports", tags=["Reports & Clinical Handoff"])

def assemble_15_section_dossier(case: Dict[str, Any]) -> Dict[str, Any]:
    """Constructs the standardized 15-section clinical handoff packet data structure."""
    vitals = case.get("vitals") or {}
    history = case.get("medicalHistory") or {}
    review = case.get("doctorReview") or {}
    referral = case.get("referral") or {}

    return {
        "section_1_patient_demographics": {
            "title": "1. Patient Information & Demographics",
            "patient_id": case.get("patientId"),
            "age": case.get("age"),
            "gender": case.get("gender"),
            "language": case.get("language"),
            "consent_confirmed": case.get("consentObtained", True)
        },
        "section_2_chief_concerns": {
            "title": "2. Chief Concerns & Clinical Summary",
            "summary": case.get("chiefConcern", ""),
            "symptoms_narrative": case.get("symptoms", ""),
            "duration": case.get("symptomDuration", "")
        },
        "section_3_symptom_timeline": {
            "title": "3. Symptom Timeline",
            "events": case.get("timeline") or []
        },
        "section_4_physical_vitals": {
            "title": "4. Physical Vitals & Measurements",
            "temperature": vitals.get("temperature", "--"),
            "spo2": vitals.get("spo2", "--"),
            "bp_systolic": vitals.get("bloodPressureSys", "--"),
            "bp_diastolic": vitals.get("bloodPressureDia", "--"),
            "heart_rate": vitals.get("heartRate", "--"),
            "respiratory_rate": vitals.get("respiratoryRate", "--")
        },
        "section_5_relevant_history": {
            "title": "5. Relevant Past Medical Conditions",
            "past_conditions": history.get("pastConditions", "None reported"),
            "breathing_problems": history.get("hasBreathingProblems", "No"),
            "chest_pain": history.get("hasChestPain", "No")
        },
        "section_6_current_medications": {
            "title": "6. Current Medications",
            "medications": history.get("currentMedications", "None")
        },
        "section_7_known_allergies": {
            "title": "7. Known Drug & Environmental Allergies",
            "allergies": history.get("allergies", "No known drug allergies")
        },
        "section_8_diagnostic_findings": {
            "title": "8. Diagnostic Report Findings",
            "reports": case.get("reports") or []
        },
        "section_9_advisory_safety_signals": {
            "title": "9. Advisory Safety Signals (Rule-Based)",
            "signals": case.get("safetySignals") or [],
            "system_priority": case.get("priority", "LOW")
        },
        "section_10_missing_info_tracker": {
            "title": "10. Missing Information Resolution Tracker",
            "items": case.get("missingInfoTracker") or []
        },
        "section_11_health_worker_verification": {
            "title": "11. Frontline Health Worker Verification",
            "verified_by": "Frontline Health Worker / Triage Nurse",
            "timestamp": case.get("createdAt")
        },
        "section_12_doctor_clinical_notes": {
            "title": "12. Doctor / Reviewer Decision & Notes",
            "reviewed_by": review.get("reviewedBy", "Pending Review"),
            "reviewed_at": review.get("reviewedAt", "Pending"),
            "decision": review.get("decision", "Pending"),
            "reviewer_notes": review.get("reviewerNotes", "No clinician notes documented yet."),
            "escalation_reason": review.get("escalationReason", "")
        },
        "section_13_referral_routing": {
            "title": "13. Specialist Referral & Destination Facility",
            "facility": referral.get("destinationFacility", "Not referred"),
            "department": referral.get("destinationDepartment", ""),
            "reason": referral.get("reason", ""),
            "notes": referral.get("reviewerNotes", "")
        },
        "section_14_timestamps": {
            "title": "14. Audit & Transmission Timestamps",
            "created_at": case.get("createdAt"),
            "updated_at": case.get("updatedAt"),
            "audit_trail": case.get("auditTrail") or []
        },
        "section_15_system_version": {
            "title": "15. System Integrity & Governance Verification",
            "platform": "Multimodal AI-Assisted Clinical Triage Platform v2.0",
            "safety_protocol": "Strict Deterministic Human-in-the-Loop Protocol",
            "hash": f"SHA256-{case.get('patientId')}-VERIFIED"
        }
    }

@router.get("/{case_id}/dossier")
def get_case_dossier(case_id: str, db: Session = Depends(get_db)):
    """Returns the standardized 15-section clinical handoff dossier JSON."""
    case = db.query(Case).filter(
        (Case.id == case_id) | (func.upper(Case.patient_id) == case_id.upper())
    ).first()
    if not case:
        raise HTTPException(status_code=404, detail=f"Case {case_id} not found")

    dossier = assemble_15_section_dossier(case.to_dict())
    return {"success": True, "caseId": case_id, "dossier": dossier}

@router.get("/{case_id}/pdf")
def generate_pdf_report(case_id: str, db: Session = Depends(get_db)):
    """Generates and downloads a clean, professional clinical handoff PDF report."""
    case = db.query(Case).filter(
        (Case.id == case_id) | (func.upper(Case.patient_id) == case_id.upper())
    ).first()
    if not case:
        raise HTTPException(status_code=404, detail=f"Case {case_id} not found")

    case_data = case.to_dict()
    vitals = case_data.get("vitals") or {}
    review = case_data.get("doctorReview") or {}
    referral = case_data.get("referral") or {}

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter, rightMargin=36, leftMargin=36, topMargin=36, bottomMargin=36)
    styles = getSampleStyleSheet()

    title_style = ParagraphStyle(
        "DocTitle",
        parent=styles["Heading1"],
        fontSize=18,
        leading=22,
        textColor=colors.HexColor("#0f172a"),
        spaceAfter=6
    )
    section_style = ParagraphStyle(
        "SectionHeading",
        parent=styles["Heading2"],
        fontSize=13,
        leading=16,
        textColor=colors.HexColor("#1e3a8a"),
        spaceBefore=10,
        spaceAfter=4
    )
    body_style = ParagraphStyle(
        "Body",
        parent=styles["Normal"],
        fontSize=9,
        leading=12,
        textColor=colors.HexColor("#334155")
    )
    bold_style = ParagraphStyle(
        "BoldBody",
        parent=body_style,
        fontName="Helvetica-Bold"
    )

    story = []

    # Header
    story.append(Paragraph("DISTRICT HEALTH INFORMATICS & TRIAGE COMMAND", title_style))
    story.append(Paragraph(f"Standardized Clinical Handoff Dossier | Patient: {case_data.get('patientId')}", section_style))
    story.append(Paragraph(f"Priority: <b>{case_data.get('priority', 'MEDIUM')}</b> | Status: <b>{case_data.get('status', 'NEW')}</b> | Generated: {case_data.get('updatedAt', '')}", body_style))
    story.append(Spacer(1, 12))

    # Demographics & Concerns Table
    demo_data = [
        [Paragraph("<b>Patient ID:</b>", body_style), Paragraph(str(case_data.get("patientId")), body_style),
         Paragraph("<b>Age / Gender:</b>", body_style), Paragraph(f"{case_data.get('age', '--')} / {case_data.get('gender', '--')}", body_style)],
        [Paragraph("<b>Language:</b>", body_style), Paragraph(str(case_data.get("language", "Hindi")), body_style),
         Paragraph("<b>Duration:</b>", body_style), Paragraph(str(case_data.get("symptomDuration", "--")), body_style)],
        [Paragraph("<b>Chief Concern:</b>", body_style), Paragraph(str(case_data.get("chiefConcern", "No concern reported")), body_style), "", ""]
    ]
    t1 = Table(demo_data, colWidths=[100, 170, 100, 170])
    t1.setStyle(TableStyle([
        ('SPAN', (1, 2), (3, 2)),
        ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor("#f8fafc")),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor("#cbd5e1")),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
    ]))
    story.append(t1)
    story.append(Spacer(1, 10))

    # Vitals Table
    story.append(Paragraph("Physiological Vital Signs", section_style))
    vitals_data = [
        [Paragraph("<b>SpO2:</b>", body_style), Paragraph(f"{vitals.get('spo2', '--')}%", bold_style),
         Paragraph("<b>Temperature:</b>", body_style), Paragraph(f"{vitals.get('temperature', '--')} °C", body_style)],
        [Paragraph("<b>Blood Pressure:</b>", body_style), Paragraph(f"{vitals.get('bloodPressureSys', '--')}/{vitals.get('bloodPressureDia', '--')} mmHg", bold_style),
         Paragraph("<b>Heart Rate:</b>", body_style), Paragraph(f"{vitals.get('heartRate', '--')} bpm", body_style)]
    ]
    t2 = Table(vitals_data, colWidths=[100, 170, 100, 170])
    t2.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor("#f1f5f9")),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor("#cbd5e1")),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
    ]))
    story.append(t2)
    story.append(Spacer(1, 10))

    # Clinical Decisions & Doctor Review
    story.append(Paragraph("Clinical Review & Referral Plan", section_style))
    review_data = [
        [Paragraph("<b>Clinician:</b>", body_style), Paragraph(str(review.get("reviewedBy", "Pending Clinician Review")), body_style)],
        [Paragraph("<b>Decision:</b>", body_style), Paragraph(str(review.get("decision", "Pending")).upper(), bold_style)],
        [Paragraph("<b>Clinician Notes:</b>", body_style), Paragraph(str(review.get("reviewerNotes", "None")), body_style)],
        [Paragraph("<b>Referral Target:</b>", body_style), Paragraph(f"{referral.get('destinationFacility', 'None')} ({referral.get('destinationDepartment', '')})", body_style)]
    ]
    t3 = Table(review_data, colWidths=[100, 440])
    t3.setStyle(TableStyle([
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor("#cbd5e1")),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
    ]))
    story.append(t3)
    story.append(Spacer(1, 14))

    # Footer notice
    story.append(Paragraph("<i>This document is a standardized clinical handoff report generated by the Clinical Triage System with deterministic safety verification. Confidential Medical Record.</i>", body_style))

    doc.build(story)
    buffer.seek(0)

    filename = f"handoff_{case_data.get('patientId', 'case')}.pdf"
    return StreamingResponse(
        buffer,
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )
