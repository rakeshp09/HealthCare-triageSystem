"""Frontend UI Route Views and Template Renderers.

Serves user-facing landing, role dashboards, intake wizard, clinical review,
and 15-section handoff dossier pages with Jinja2 templates and multilingual support.
"""

import os
import secrets
from datetime import datetime
from functools import wraps
from flask import Blueprint, render_template, request, redirect, url_for, flash, session, jsonify
from sqlalchemy import func

from backend.app.config import settings
from backend.app.database import SessionLocal
from backend.app.models import User, Case, ElectronicHealthRecord, SharedRecordLink, Testimonial
from backend.app.reports import assemble_15_section_dossier
from backend.app.security import verify_password, create_access_token, hash_password
from backend.services.safety_service import safety_service
from backend.services.rag_service import rag_service
from backend.services.extraction_service import extraction_service
from backend.services.vision_service import vision_service
from backend.utils.helpers import get_current_timestamp, format_file_size, sanitize_filename
from .forms import ContactForm

frontend_bp = Blueprint("frontend", __name__, template_folder="templates", static_folder="static")
auth_bp = Blueprint("auth", __name__)
backend_bp = Blueprint("backend", __name__)

def get_current_user():
    """Retrieves current authenticated user from Flask session or cookies."""
    user_id = session.get("user_id") or request.cookies.get("user_id")
    if not user_id:
        return None
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.id == user_id).first()
        if not user or user.status.upper() != "ACTIVE":
            return None
        return user.to_dict()
    finally:
        db.close()

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        user = get_current_user()
        if not user:
            return redirect(url_for("frontend.login_view"))
        return f(*args, **kwargs)
    return decorated_function

def role_required(*allowed_roles):
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            user = get_current_user()
            if not user:
                return redirect(url_for("frontend.login_view"))
            user_role = user.get("role", "")
            matches = any(role.lower() in user_role.lower() for role in allowed_roles)
            if not matches and "Admin" not in user_role:
                return redirect(url_for("frontend.dashboard"))
            return f(*args, **kwargs)
        return decorated_function
    return decorator

# -----------------
# PUBLIC PAGES
# -----------------

@frontend_bp.route("/")
def home():
    """Landing page featuring hero, 6-step architecture breakdown, 3 pillars, and quick demo."""
    user = get_current_user()
    return render_template("home.html", user=user)

@frontend_bp.route("/about")
def about():
    """Explains clinical safety principles, human-in-the-loop governance, and multimodal AI."""
    user = get_current_user()
    return render_template("about.html", user=user)

@frontend_bp.route("/testimonials", endpoint="testimonials")
@frontend_bp.route("/testimonials", endpoint="testimonials_view")
def testimonials():
    """Patient stories, verified clinical outcomes, and regional care testimonials."""
    user = get_current_user()
    db = SessionLocal()
    try:
        testimonials_list = [t.to_dict() for t in db.query(Testimonial).order_by(Testimonial.created_at.desc()).all()]
    finally:
        db.close()
    return render_template("testimonials.html", user=user, testimonials=testimonials_list)

@frontend_bp.route("/set-language/<lang_code>")
def set_language(lang_code):
    """Switch user interface language (en, hi, or)."""
    if lang_code in ["en", "hi", "or"]:
        session["lang"] = lang_code
    target = request.referrer or url_for("frontend.home")
    return redirect(target)

@frontend_bp.route("/contact", methods=["GET", "POST"])
def contact():
    """Facility contact directory, technical informatics command, and feedback form."""
    user = get_current_user()
    success_msg = None
    if request.method == "POST":
        is_valid, errors = ContactForm.validate(request.form)
        if is_valid:
            success_msg = "Thank you. Your message has been routed to the District Health Informatics Command."
        else:
            for err in errors:
                flash(err, "error")
    return render_template("contact.html", user=user, success_msg=success_msg)

# -----------------
# AUTHENTICATION VIEWS
# -----------------

@frontend_bp.route("/login", methods=["GET", "POST"], endpoint="login_view")
def login_view():
    """Authentication login view with JSON and form submission support."""
    if request.method == "POST":
        is_json = request.is_json or "application/json" in request.headers.get("Accept", "") or request.headers.get("X-Requested-With") == "XMLHttpRequest"
        data = request.get_json(silent=True) if request.is_json else request.form
        if not data:
            data = request.form

        username = (data.get("username") or "").strip().lower()
        password = (data.get("password") or "").strip()

        db = SessionLocal()
        try:
            user = db.query(User).filter(func.lower(User.username) == username).first()
            if not user or not verify_password(password, user.password_hash, user.salt):
                msg = "Invalid username or password"
                if is_json:
                    return jsonify({"success": False, "message": msg}), 401
                flash(msg, "error")
                return render_template("login.html", error=msg, username=username)

            if user.status.upper() == "PENDING":
                msg = "Your staff account is awaiting administrative approval."
                if is_json:
                    return jsonify({"success": False, "message": msg}), 403
                flash(msg, "error")
                return render_template("login.html", error=msg, username=username)

            if user.status.upper() == "REJECTED":
                msg = "Your account has been rejected. Please contact administrator."
                if is_json:
                    return jsonify({"success": False, "message": msg}), 403
                flash(msg, "error")
                return render_template("login.html", error=msg, username=username)

            session["user_id"] = user.id
            session.permanent = True

            role = user.role
            if role == "Admin":
                redirect_url = url_for("frontend.admin_dashboard")
            elif "Doctor" in role or "Reviewer" in role:
                redirect_url = url_for("frontend.doctor_dashboard")
            elif role == "Patient":
                redirect_url = url_for("frontend.patient_dashboard")
            else:
                redirect_url = url_for("frontend.nurse_dashboard")

            token = create_access_token(data={"sub": user.id, "username": user.username, "role": user.role})
            success_msg = "Login successful"

            if is_json:
                resp = jsonify({
                    "success": True,
                    "message": success_msg,
                    "redirect": redirect_url,
                    "user": user.to_dict(),
                    "access_token": token
                })
                resp.set_cookie("user_id", user.id, max_age=86400, samesite="lax")
                resp.set_cookie("access_token", token, max_age=86400, samesite="lax")
                resp.set_cookie("token", token, max_age=86400, samesite="lax")
                return resp

            flash(success_msg, "success")
            resp = redirect(redirect_url)
            resp.set_cookie("user_id", user.id, max_age=86400, samesite="lax")
            resp.set_cookie("access_token", token, max_age=86400, samesite="lax")
            resp.set_cookie("token", token, max_age=86400, samesite="lax")
            return resp
        finally:
            db.close()

    err_param = request.args.get("error") or request.args.get("msg")
    return render_template("login.html", error=err_param)

@frontend_bp.route("/signup", methods=["GET", "POST"], endpoint="signup_view")
def signup_view():
    """Role registration and user sign up view with JSON and form submission support."""
    if request.method == "POST":
        is_json = request.is_json or "application/json" in request.headers.get("Accept", "") or request.headers.get("X-Requested-With") == "XMLHttpRequest"
        data = request.get_json(silent=True) if request.is_json else request.form
        if not data:
            data = request.form

        name = (data.get("name") or "").strip()
        username = (data.get("username") or "").strip().lower()
        password = (data.get("password") or "").strip()
        confirm_password = (data.get("confirm_password") or data.get("confirmPassword") or "").strip()
        email = (data.get("email") or "").strip() or None
        role = (data.get("role") or "Patient").strip()
        facility = (data.get("facility") or "").strip() or None
        salutation = (data.get("salutation") or "Mr").strip()
        dob = (data.get("dob") or data.get("date_of_birth") or "").strip()
        gender = (data.get("gender") or "Male").strip()
        guardian_relation = (data.get("guardian_relation") or data.get("guardianRelation") or "C/O").strip()
        guardian_name = (data.get("guardian_name") or data.get("guardianName") or "").strip()

        if not name or not password:
            msg = "Full name and password are required."
            if is_json:
                return jsonify({"success": False, "message": msg}), 400
            flash(msg, "error")
            return render_template("signup.html", error=msg)

        if confirm_password and password != confirm_password:
            msg = "Passwords do not match / पासवर्ड मेल नहीं खाते"
            if is_json:
                return jsonify({"success": False, "message": msg}), 400
            flash(msg, "error")
            return render_template("signup.html", error=msg)

        # Generate unique username if not explicitly provided
        if not username:
            import re
            base = re.sub(r'[^a-z0-9]', '', (name or "patient").lower())
            if not base:
                base = "patient"
            username = f"{base}_{secrets.token_hex(2)}"

        db = SessionLocal()
        try:
            existing = db.query(User).filter(func.lower(User.username) == username).first()
            if existing:
                msg = f"Username '{username}' is already taken."
                if is_json:
                    return jsonify({"success": False, "message": msg}), 409
                flash(msg, "error")
                return render_template("signup.html", error=msg)

            creds = hash_password(password)
            user_id = f"usr_{secrets.token_hex(6)}"
            now = datetime.now().strftime("%Y-%m-%d %I:%M %p")
            is_patient = role.lower() == "patient"
            user_status = "ACTIVE" if is_patient else "PENDING"

            display_name = f"{salutation} {name}".strip() if salutation and not name.startswith(salutation) else name

            new_user = User(
                id=user_id,
                name=display_name,
                username=username,
                email=email,
                password_hash=creds["hash"],
                salt=creds["salt"],
                role=role,
                status=user_status,
                facility=facility,
                created_at=now,
                updated_at=now
            )
            db.add(new_user)
            db.commit()

            if is_patient:
                ehr_id = f"ehr_{secrets.token_hex(4)}"
                demographics = {
                    "salutation": salutation,
                    "fullName": name,
                    "displayName": display_name,
                    "dob": dob,
                    "gender": gender,
                    "guardianRelation": guardian_relation,
                    "guardianName": guardian_name,
                    "email": email
                }
                ehr = ElectronicHealthRecord(
                    id=ehr_id,
                    patient_id=username,
                    vitals={"demographics": demographics},
                    prescriptions=[],
                    reports=[]
                )
                db.add(ehr)
                db.commit()

            token = create_access_token(data={"sub": user_id, "username": username, "role": role})

            if is_patient:
                session["user_id"] = user_id
                session.permanent = True
                redirect_url = url_for("frontend.patient_dashboard")
            else:
                redirect_url = url_for("auth.login_view")

            success_msg = "Account created successfully"

            if is_json:
                resp = jsonify({
                    "success": True,
                    "message": success_msg,
                    "redirect": redirect_url,
                    "user": new_user.to_dict(),
                    "access_token": token
                })
                resp.set_cookie("user_id", user_id, max_age=86400, samesite="lax")
                resp.set_cookie("access_token", token, max_age=86400, samesite="lax")
                resp.set_cookie("token", token, max_age=86400, samesite="lax")
                return resp, 201

            flash(success_msg, "success")
            resp = redirect(redirect_url)
            resp.set_cookie("user_id", user_id, max_age=86400, samesite="lax")
            resp.set_cookie("access_token", token, max_age=86400, samesite="lax")
            resp.set_cookie("token", token, max_age=86400, samesite="lax")
            return resp
        finally:
            db.close()

    return render_template("signup.html")

@frontend_bp.route("/logout")
def logout_view():
    """Logs user out of session."""
    session.clear()
    resp = redirect(url_for("frontend.home"))
    resp.delete_cookie("user_id")
    resp.delete_cookie("access_token")
    resp.delete_cookie("token")
    return resp

# Compatibility routes for templates calling url_for('auth.*')
@auth_bp.route("/login", methods=["GET", "POST"], endpoint="login_view")
def auth_login_view():
    return login_view()

@auth_bp.route("/signup", methods=["GET", "POST"], endpoint="signup_view")
def auth_signup_view():
    return signup_view()

@auth_bp.route("/logout", endpoint="logout_view")
def auth_logout_view():
    return logout_view()

# -----------------
# ROLE DASHBOARDS
# -----------------

@frontend_bp.route("/dashboard")
def dashboard():
    """Role-aware workspace redirector."""
    user = get_current_user()
    if not user:
        return redirect(url_for("frontend.login_view"))

    role = user.get("role", "")
    if role == "Admin":
        return redirect(url_for("frontend.admin_dashboard"))
    elif "Doctor" in role or "Reviewer" in role:
        return redirect(url_for("frontend.doctor_dashboard"))
    elif role == "Patient":
        return redirect(url_for("frontend.patient_dashboard"))
    else:
        return redirect(url_for("frontend.nurse_dashboard"))

@frontend_bp.route("/patient/dashboard", endpoint="patient_dashboard")
@frontend_bp.route("/patient-dashboard")
@login_required
@role_required("Patient", "Admin")
def patient_dashboard():
    """Renders patient portal with vitals, prescriptions, reports, and diet planner."""
    user = get_current_user()
    username = user["username"]
    db = SessionLocal()
    try:
        ehr = db.query(ElectronicHealthRecord).filter(
            (ElectronicHealthRecord.patient_id == username) |
            (ElectronicHealthRecord.patient_id == user["id"])
        ).first()

        ehr_dict = ehr.to_dict() if ehr else {"patient_id": username, "vitals": {}, "prescriptions": [], "reports": []}
        active_links = [l.to_dict() for l in (ehr.shared_links if ehr else []) if l.is_valid()]
        
        all_cases = [c.to_dict() for c in db.query(Case).all()]
        patient_cases = [c for c in all_cases if c.get("patientId", "").lower() in {username.lower(), user["id"].lower()}]
    finally:
        db.close()

    return render_template(
        "patient/dashboard.html",
        user=user,
        ehr=ehr_dict,
        active_links=active_links,
        cases=patient_cases
    )

@frontend_bp.route("/doctor/dashboard", endpoint="doctor_dashboard")
@frontend_bp.route("/doctor-dashboard")
@login_required
@role_required("Doctor", "Reviewer", "Admin")
def doctor_dashboard():
    """Renders doctor clinical workstation with IoT charts and triage queue."""
    user = get_current_user()
    db = SessionLocal()
    try:
        all_cases = [c.to_dict() for c in db.query(Case).order_by(Case.created_at.desc()).all()]
        doctor_cases = [c for c in all_cases if c.get("status") in {"READY_FOR_REVIEW", "REVIEWED", "ESCALATED", "REFERRED"}]
    finally:
        db.close()

    return render_template(
        "doctor/dashboard.html",
        user=user,
        cases=doctor_cases,
        all_cases=all_cases
    )

@frontend_bp.route("/nurse/dashboard", endpoint="nurse_dashboard")
@frontend_bp.route("/nurse-dashboard")
@login_required
@role_required("Health Worker", "Nurse", "Admin")
def nurse_dashboard():
    """Renders frontline health worker admission queue and intake desk."""
    user = get_current_user()
    db = SessionLocal()
    try:
        cases = [c.to_dict() for c in db.query(Case).order_by(Case.created_at.desc()).all()]
    finally:
        db.close()
    return render_template("nurse/dashboard.html", user=user, cases=cases)

@frontend_bp.route("/admin/dashboard", endpoint="admin_dashboard")
@frontend_bp.route("/admin-dashboard")
@login_required
@role_required("Admin")
def admin_dashboard():
    """Renders administrative governance portal."""
    user = get_current_user()
    db = SessionLocal()
    try:
        users = [u.to_dict() for u in db.query(User).order_by(User.created_at.desc()).all()]
        cases = [c.to_dict() for c in db.query(Case).order_by(Case.created_at.desc()).all()]
    finally:
        db.close()
    return render_template("admin/dashboard.html", user=user, users=users, cases=cases)

# Compatibility routes for templates calling url_for('backend.*')
@backend_bp.route("/nurse-dashboard", endpoint="nurse_dashboard")
def backend_nurse_dash():
    return nurse_dashboard()

@backend_bp.route("/doctor-dashboard", endpoint="doctor_dashboard")
def backend_doctor_dash():
    return doctor_dashboard()

@backend_bp.route("/patient-dashboard", endpoint="patient_dashboard")
def backend_patient_dash():
    return patient_dashboard()

@backend_bp.route("/admin-dashboard", endpoint="admin_dashboard")
def backend_admin_dash():
    return admin_dashboard()

@backend_bp.route("/logout", endpoint="logout_view")
def backend_logout_view():
    return logout_view()

# -----------------
# CASE DIRECTORY & DOSSIERS
# -----------------

@frontend_bp.route("/cases")
@login_required
def case_directory():
    """Case directory with status, priority, language, and search filtering."""
    user = get_current_user()
    filters = {
        "status": request.args.get("status"),
        "priority": request.args.get("priority"),
        "language": request.args.get("language"),
        "search": request.args.get("search")
    }

    db = SessionLocal()
    try:
        query = db.query(Case).order_by(Case.created_at.desc())
        if filters["status"] and filters["status"] != "ALL":
            query = query.filter(Case.status == filters["status"])
        if filters["priority"] and filters["priority"] != "ALL":
            query = query.filter(Case.priority == filters["priority"])
        if filters["language"] and filters["language"] != "ALL":
            query = query.filter(Case.language == filters["language"])

        cases = [c.to_dict() for c in query.all()]

        # RBAC: In /cases route, filter by user_id=session['user_id'] when role='patient'
        # Health worker/admin roles retain full visibility.
        user_role = (user.get("role") or "").lower() if user else ""
        session_user_id = session.get("user_id")
        if user_role == "patient" and session_user_id:
            patient_keys = {
                str(session_user_id).lower(),
                str(user.get("id", "")).lower(),
                str(user.get("username", "")).lower()
            }
            cases = [
                c for c in cases
                if str(c.get("patientId", "")).lower() in patient_keys
                or str(c.get("id", "")).lower() in patient_keys
                or str(c.get("user_id", "")).lower() in patient_keys
                or str(c.get("userId", "")).lower() in patient_keys
            ]

        if filters["search"]:
            q = filters["search"].lower().strip()
            cases = [
                c for c in cases
                if q in c.get("patientId", "").lower()
                or q in (c.get("chiefConcern") or "").lower()
                or q in (c.get("symptoms") or "").lower()
                or q in c.get("language", "").lower()
            ]
    finally:
        db.close()

    return render_template("case_directory.html", user=user, cases=cases, filters=filters)

@frontend_bp.route("/extract_entities", methods=["GET", "POST"])
@frontend_bp.route("/api/extract_entities", methods=["GET", "POST"])
def frontend_extract_entities():
    """RAG-based clinical entity extraction and schema verification."""
    data = {}
    if request.is_json:
        data = request.get_json(silent=True) or {}
    elif request.form:
        data = dict(request.form)

    text = data.get("text") or data.get("findings") or data.get("narrative") or ""
    report_data = data.get("report")
    existing_case = data.get("case_data") or data.get("existing_data") or {}

    result = rag_service.extract_entities_and_check_schema(
        text=text,
        report_data=report_data,
        existing_data=existing_case
    )
    if report_data and "report" not in result:
        result["report"] = report_data

    return jsonify(result)

@frontend_bp.route("/upload_report", methods=["POST"])
@frontend_bp.route("/api/upload_report", methods=["POST"])
@frontend_bp.route("/upload-report", methods=["POST"])
@frontend_bp.route("/api/upload-report", methods=["POST"])
def upload_report_view():
    """Uploads diagnostic scan or medical report, returning metadata and attaching only upon confirmation."""
    file = (
        request.files.get("file")
        or request.files.get("document")
        or request.files.get("report")
        or request.files.get("reportFile")
    )
    if not file or not file.filename:
        return jsonify({"success": False, "message": "No file provided"}), 400

    # Determine confirmation status
    confirm_val = (
        request.form.get("isConfirmed")
        or request.form.get("confirm")
        or request.form.get("is_confirmed")
        or (request.get_json(silent=True) or {}).get("isConfirmed")
        or (request.get_json(silent=True) or {}).get("confirm")
    )
    is_confirmed_bool = (confirm_val is True or str(confirm_val).lower() in ("true", "1", "yes"))

    orig_name = file.filename
    base_name, ext = os.path.splitext(orig_name)
    ext = ext.lower()
    if ext not in [".png", ".jpg", ".jpeg", ".pdf", ".webp", ".txt"]:
        ext = ".pdf"

    clean_base = sanitize_filename(base_name)
    filename = f"{clean_base}_{secrets.token_hex(3)}{ext}"
    os.makedirs(settings.UPLOAD_FOLDER, exist_ok=True)
    save_path = os.path.join(settings.UPLOAD_FOLDER, filename)
    file.save(save_path)

    file_size_bytes = os.path.getsize(save_path)
    file_size_display = format_file_size(file_size_bytes)
    ocr_result = vision_service.process_document(save_path)

    report_data = {
        "id": f"rep-{secrets.token_hex(3)}",
        "fileName": filename,
        "originalName": orig_name,
        "fileType": ocr_result.get("report_type", "Medical Document"),
        "fileSize": file_size_display,
        "uploadedAt": get_current_timestamp(),
        "reportType": ocr_result.get("report_type", "Medical Document"),
        "findings": ocr_result.get("findings", ""),
        "impressions": ocr_result.get("impressions", []),
        "flags": ocr_result.get("flags", []),
        "ocrConfidence": ocr_result.get("ocr_confidence", 0.94),
        "url": f"/static/uploads/{filename}",
        "previewUrl": f"/static/uploads/{filename}",
        "attached": is_confirmed_bool,
        "isConfirmed": is_confirmed_bool
    }

    # Only save to patient record in DB when explicit confirmation is given
    case_id = request.form.get("case_id") or request.form.get("patient_id")
    if case_id and is_confirmed_bool:
        db = SessionLocal()
        try:
            case = db.query(Case).filter((Case.id == case_id) | (Case.patient_id == case_id)).first()
            if case:
                case_data = case.to_dict()
                reports = case_data.get("reports") or []
                reports.append(report_data)
                case_data["reports"] = reports
                case.data = case_data
                case.updated_at = get_current_timestamp()
                db.commit()
        finally:
            db.close()

    return jsonify({
        "success": True,
        "isConfirmed": is_confirmed_bool,
        "attached": is_confirmed_bool,
        "report": report_data,
        "filename": filename,
        "originalName": orig_name,
        "fileSize": file_size_display,
        "fileType": report_data["fileType"],
        "reportUrl": report_data["url"],
        "message": (
            "Report confirmed and attached to patient record."
            if is_confirmed_bool
            else "File metadata generated. Explicit confirmation required to attach to patient record."
        )
    })

@frontend_bp.route("/cases/new")
@login_required
def new_case_wizard():
    """5-Step Patient Intake Wizard (Demographics, Multimodal Input, AI Analysis, Vitals, Review)."""
    user = get_current_user()
    return render_template("new_case_wizard.html", user=user)

@frontend_bp.route("/case/<case_id>")
def case_detail(case_id):
    """Case Detail Dossier (Overview, Vitals, Reports, Timeline, Audit Trail)."""
    user = get_current_user()
    db = SessionLocal()
    try:
        case_obj = db.query(Case).filter((Case.id == case_id) | (func.upper(Case.patient_id) == case_id.upper())).first()
        if not case_obj:
            flash(f"Patient case {case_id} was not found.", "error")
            return redirect(url_for("frontend.home"))
        case = case_obj.to_dict()
    finally:
        db.close()
    return render_template("case_detail.html", user=user, case=case)

@frontend_bp.route("/case/<case_id>/review")
@login_required
def case_review(case_id):
    """Doctor clinical review workspace: inspect audio, scans, edit extractions, sign off."""
    user = get_current_user()
    db = SessionLocal()
    try:
        case_obj = db.query(Case).filter((Case.id == case_id) | (func.upper(Case.patient_id) == case_id.upper())).first()
        if not case_obj:
            flash(f"Patient case {case_id} was not found.", "error")
            return redirect(url_for("frontend.home"))
        case = case_obj.to_dict()
    finally:
        db.close()
    return render_template("case_review.html", user=user, case=case)

@frontend_bp.route("/case/<case_id>/handoff")
def case_handoff(case_id):
    """15-Section Standardized Clinical Handoff Dossier ready for print, PDF, JSON, and text export."""
    user = get_current_user()
    db = SessionLocal()
    try:
        case_obj = db.query(Case).filter((Case.id == case_id) | (func.upper(Case.patient_id) == case_id.upper())).first()
        if not case_obj:
            flash(f"Patient case {case_id} was not found.", "error")
            return redirect(url_for("frontend.home"))
        case = case_obj.to_dict()
    finally:
        db.close()

    dossier_sections = assemble_15_section_dossier(case)
    return render_template("case_handoff.html", user=user, case=case, sections=dossier_sections)

@frontend_bp.route("/case/<case_id>/referral")
@login_required
def case_referral(case_id):
    """Specialist referral form for high-risk patient transfers."""
    user = get_current_user()
    db = SessionLocal()
    try:
        case_obj = db.query(Case).filter((Case.id == case_id) | (func.upper(Case.patient_id) == case_id.upper())).first()
        if not case_obj:
            flash(f"Patient case {case_id} was not found.", "error")
            return redirect(url_for("frontend.home"))
        case = case_obj.to_dict()
    finally:
        db.close()
    return render_template("case_referral.html", user=user, case=case)

@frontend_bp.route("/shared/<token>")
def view_shared_record(token: str):
    """Public portal to inspect patient EHR via authorized temporary share link."""
    db = SessionLocal()
    try:
        link = db.query(SharedRecordLink).filter_by(secure_token=token).first()
        if not link or not link.is_valid():
            return render_template("base.html", error="This shared medical record link is invalid or has expired.")

        ehr = link.record
        patient_user = db.query(User).filter_by(username=ehr.patient_id).first()
        return render_template(
            "patient/shared_record.html",
            ehr=ehr.to_dict(),
            link=link.to_dict(),
            patient=patient_user.to_dict() if patient_user else {"name": "Patient", "username": ehr.patient_id}
        )
    finally:
        db.close()

@frontend_bp.route("/cases/<case_id>/approve-admission", methods=["POST"])
@frontend_bp.route("/cases/<case_id>/approve", methods=["POST"])
@frontend_bp.route("/api/cases/<case_id>/approve-admission", methods=["POST"])
@frontend_bp.route("/api/cases/<case_id>/approve", methods=["POST"])
def frontend_approve_admission(case_id):
    """Fallback handler for nurse admission approval and vitals verification."""
    clean_id = str(case_id).strip()
    db = SessionLocal()
    try:
        case = db.query(Case).filter(
            (Case.id == clean_id) |
            (func.lower(Case.id) == clean_id.lower()) |
            (Case.patient_id == clean_id) |
            (func.lower(Case.patient_id) == clean_id.lower())
        ).first()

        if not case:
            return jsonify({"status": "error", "message": f"Case '{case_id}' not found", "detail": f"Case '{case_id}' not found"}), 404

        payload = request.get_json(silent=True) or {}
        case_data = case.to_dict()

        vitals = dict(case_data.get("vitals") or {})
        if payload.get("vitals") and isinstance(payload["vitals"], dict):
            for k, v in payload["vitals"].items():
                if v is not None and str(v).strip() != "":
                    vitals[k] = v

        for k in ["temp", "temperature", "spo2", "heart_rate", "heartRate", "pulse", "blood_pressure", "bp"]:
            val = payload.get(k)
            if val is not None and str(val).strip() != "":
                norm_key = "heartRate" if k in ("heart_rate", "pulse") else ("temperature" if k == "temp" else ("bloodPressure" if k in ("bp", "blood_pressure") else k))
                vitals[norm_key] = val

        if vitals:
            case_data["vitals"] = vitals
            priority, signals, missing = safety_service.evaluate(case_data)
            case_data["priority"] = priority
            case_data["safetySignals"] = signals
            case_data["missingInfoTracker"] = missing

        now = get_current_timestamp()
        case_data["status"] = "READY_FOR_REVIEW"
        case_data["updatedAt"] = now

        current_user = get_current_user()
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

        return jsonify({
            "status": "success",
            "message": "Case admission approved successfully",
            "caseData": case_data
        }), 200
    finally:
        db.close()


# -----------------
# HEALTH & EHR PORTAL
# -----------------

@frontend_bp.route("/health", endpoint="health_page")
@frontend_bp.route("/health-records", endpoint="health_records")
def health_page():
    """Bilingual comprehensive health page (Summary, General, Assessments, Screenings, Pathology, Vitals, Prescriptions, History)."""
    user = get_current_user()
    if not user:
        return redirect(url_for("frontend.login_view"))

    username = user["username"]
    db = SessionLocal()
    try:
        ehr = db.query(ElectronicHealthRecord).filter(
            (ElectronicHealthRecord.patient_id == username) |
            (ElectronicHealthRecord.patient_id == user["id"])
        ).first()

        ehr_dict = ehr.to_dict() if ehr else {"patient_id": username, "vitals": {}, "prescriptions": [], "reports": []}
        active_links = [l.to_dict() for l in (ehr.shared_links if ehr else []) if l.is_valid()]

        all_cases = [c.to_dict() for c in db.query(Case).all()]
        patient_cases = [c for c in all_cases if c.get("patientId", "").lower() in {username.lower(), user["id"].lower()}]
    finally:
        db.close()

    return render_template(
        "health.html",
        user=user,
        ehr=ehr_dict,
        active_links=active_links,
        cases=patient_cases
    )


# -----------------
# PROFILE & ACCOUNT MANAGEMENT
# -----------------

@frontend_bp.route("/profile", endpoint="profile_page")
def profile_page():
    """User profile page with family, referrals, addresses, wallet, invoices, support, consents, preferences, and policies."""
    user = get_current_user()
    if not user:
        return redirect(url_for("frontend.login_view"))

    username = user["username"]
    db = SessionLocal()
    try:
        ehr = db.query(ElectronicHealthRecord).filter(
            (ElectronicHealthRecord.patient_id == username) |
            (ElectronicHealthRecord.patient_id == user["id"])
        ).first()

        ehr_dict = ehr.to_dict() if ehr else {"patient_id": username, "vitals": {}, "prescriptions": [], "reports": []}
        all_cases = [c.to_dict() for c in db.query(Case).all()]
        patient_cases = [c for c in all_cases if c.get("patientId", "").lower() in {username.lower(), user["id"].lower()}]
    finally:
        db.close()

    return render_template(
        "profile.html",
        user=user,
        ehr=ehr_dict,
        cases=patient_cases
    )

@frontend_bp.route("/profile/delete-account", methods=["POST"])
@frontend_bp.route("/api/profile/delete-account", methods=["POST"])
def delete_account():
    """Deletes current user account and clears active session."""
    user = get_current_user()
    if not user:
        return jsonify({"success": False, "message": "Authentication required"}), 401

    db = SessionLocal()
    try:
        user_obj = db.query(User).filter(User.id == user["id"]).first()
        if user_obj:
            db.delete(user_obj)
            db.commit()
    finally:
        db.close()

    session.clear()
    resp = jsonify({
        "success": True,
        "message": "Your account has been deleted successfully.",
        "redirect": url_for("frontend.home")
    })
    resp.delete_cookie("user_id")
    resp.delete_cookie("access_token")
    resp.delete_cookie("token")
    return resp


# -----------------
# CASE MANAGEMENT CONTROLS (DELETE, REJECT, FORWARD)
# -----------------

@frontend_bp.route("/cases/<case_id>/delete", methods=["POST", "DELETE"])
@frontend_bp.route("/api/cases/<case_id>/delete", methods=["POST", "DELETE"])
@frontend_bp.route("/patient/<case_id>/delete", methods=["POST", "DELETE"])
@frontend_bp.route("/api/patient/<case_id>/delete", methods=["POST", "DELETE"])
def delete_case_record(case_id):
    """Deletes or archives a patient case record from the clinical database."""
    clean_id = str(case_id).strip()
    db = SessionLocal()
    try:
        case = db.query(Case).filter(
            (Case.id == clean_id) |
            (func.lower(Case.id) == clean_id.lower()) |
            (Case.patient_id == clean_id) |
            (func.lower(Case.patient_id) == clean_id.lower())
        ).first()

        if not case:
            return jsonify({"success": False, "status": "error", "message": f"Patient record '{case_id}' not found"}), 404

        db.delete(case)
        db.commit()
        return jsonify({
            "success": True,
            "status": "success",
            "message": "Patient record deleted successfully / मरीज का रिकॉर्ड सफलतापूर्वक हटा दिया गया है"
        }), 200
    finally:
        db.close()

@frontend_bp.route("/cases/<case_id>/reject", methods=["POST"])
@frontend_bp.route("/api/cases/<case_id>/reject", methods=["POST"])
def reject_case_intake(case_id):
    """Rejects patient intake with audit trail recording."""
    clean_id = str(case_id).strip()
    db = SessionLocal()
    try:
        case = db.query(Case).filter(
            (Case.id == clean_id) |
            (func.lower(Case.id) == clean_id.lower()) |
            (Case.patient_id == clean_id) |
            (func.lower(Case.patient_id) == clean_id.lower())
        ).first()

        if not case:
            return jsonify({"success": False, "status": "error", "message": f"Case '{case_id}' not found"}), 404

        payload = request.get_json(silent=True) or request.form or {}
        reason = payload.get("reason", "Intake criteria not met upon clinical review")
        now = get_current_timestamp()
        current_user = get_current_user()
        actor_name = current_user.get("name", "Clinician") if current_user else "Clinician"
        actor_role = current_user.get("role", "Doctor") if current_user else "Doctor"

        case_data = case.to_dict()
        case_data["status"] = "REJECTED"
        case_data["updatedAt"] = now

        audit = case_data.get("auditTrail") or []
        audit.append({
            "timestamp": now,
            "actor": actor_name,
            "role": actor_role,
            "action": f"Intake rejected. Reason: {reason}"
        })
        case_data["auditTrail"] = audit

        case.status = "REJECTED"
        case.data = case_data
        case.updated_at = now
        db.commit()

        return jsonify({
            "success": True,
            "status": "success",
            "message": "Patient intake rejected successfully / मरीज का इनटेक अस्वीकार कर दिया गया",
            "caseData": case_data
        }), 200
    finally:
        db.close()

@frontend_bp.route("/cases/<case_id>/forward", methods=["POST"])
@frontend_bp.route("/api/cases/<case_id>/forward", methods=["POST"])
def forward_case_to_doctor(case_id):
    """Health worker forwards case to doctor queue."""
    clean_id = str(case_id).strip()
    db = SessionLocal()
    try:
        case = db.query(Case).filter(
            (Case.id == clean_id) |
            (func.lower(Case.id) == clean_id.lower()) |
            (Case.patient_id == clean_id) |
            (func.lower(Case.patient_id) == clean_id.lower())
        ).first()

        if not case:
            return jsonify({"success": False, "status": "error", "message": f"Case '{case_id}' not found"}), 404

        now = get_current_timestamp()
        current_user = get_current_user()
        actor_name = current_user.get("name", "Health Worker") if current_user else "Health Worker"
        actor_role = current_user.get("role", "Nurse") if current_user else "Nurse"

        case_data = case.to_dict()
        case_data["status"] = "READY_FOR_REVIEW"
        case_data["updatedAt"] = now

        audit = case_data.get("auditTrail") or []
        audit.append({
            "timestamp": now,
            "actor": actor_name,
            "role": actor_role,
            "action": f"Case forwarded to attending physician queue by {actor_name} ({actor_role})."
        })
        case_data["auditTrail"] = audit

        case.status = "READY_FOR_REVIEW"
        case.data = case_data
        case.updated_at = now
        db.commit()

        return jsonify({
            "success": True,
            "status": "success",
            "message": "Case forwarded to doctor review queue / केस डॉक्टर समीक्षा कतार में भेज दिया गया",
            "caseData": case_data
        }), 200
    finally:
        db.close()


