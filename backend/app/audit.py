"""Audit Logs, Governance, and Testimonials Router.

Provides immutable access logs, case audit tracking, and patient/clinician testimonials.
"""

from typing import Dict, Any, List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from .database import get_db
from .models import Case, AuditLog, Testimonial
from .security import require_role

router = APIRouter(prefix="/api", tags=["Audit & Governance"])

@router.get("/audit/logs")
def get_audit_logs(
    limit: int = 50,
    case_id: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """Returns chronologically ordered audit logs for regulatory and clinical compliance."""
    logs = []
    cases = db.query(Case).all()
    for c in cases:
        cdata = c.to_dict()
        trail = cdata.get("auditTrail") or []
        for entry in trail:
            if not case_id or c.patient_id.lower() == case_id.lower():
                logs.append({
                    "case_id": c.patient_id,
                    "timestamp": entry.get("timestamp"),
                    "actor": entry.get("actor"),
                    "role": entry.get("role"),
                    "action": entry.get("action")
                })

    logs.sort(key=lambda x: x.get("timestamp") or "", reverse=True)
    return {"success": True, "count": len(logs[:limit]), "logs": logs[:limit]}

@router.get("/audit/cases/{case_id}")
def get_case_audit(case_id: str, db: Session = Depends(get_db)):
    """Returns granular audit chain-of-custody for a specific patient case."""
    case = db.query(Case).filter(
        (Case.id == case_id) | (Case.patient_id == case_id)
    ).first()
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")

    case_data = case.to_dict()
    return {
        "success": True,
        "case_id": case.patient_id,
        "auditTrail": case_data.get("auditTrail") or []
    }

@router.get("/testimonials")
def get_testimonials(db: Session = Depends(get_db)):
    """Returns verified patient and clinician testimonials."""
    testimonials = db.query(Testimonial).order_by(Testimonial.created_at.desc()).all()
    return {"testimonials": [t.to_dict() for t in testimonials]}
