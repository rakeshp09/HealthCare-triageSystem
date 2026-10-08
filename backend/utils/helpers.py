"""Common Helper Utilities, Sanitizers, Formatters, Decorators, and Multilingual i18n Helpers.
"""

import os
import re
import secrets
from datetime import datetime
from functools import wraps
from typing import Dict, Any, Optional

TRANSLATIONS = {
    "en": {},
    "hi": {},
    "or": {}
}

def load_translations(base_dir: str):
    """Loads .po message catalogs from frontend/i18n into in-memory cache."""
    i18n_dir = os.path.join(base_dir, "frontend", "i18n")
    for lang in ["en", "hi", "or"]:
        po_path = os.path.join(i18n_dir, lang, "messages.po")
        if os.path.exists(po_path):
            try:
                with open(po_path, "r", encoding="utf-8") as f:
                    content = f.read()
                matches = re.findall(r'msgid\s+"(.*)"\s*\nmsgstr\s+"(.*)"', content)
                for msgid, msgstr in matches:
                    if msgid and msgstr:
                        TRANSLATIONS[lang][msgid] = msgstr
            except Exception as e:
                print(f"[i18n] Error loading {po_path}: {e}")

def gettext(message: str, lang: Optional[str] = None) -> str:
    """Translates message using active session language or specified language code."""
    if not lang:
        try:
            from flask import session
            lang = session.get("lang", "en")
        except Exception:
            lang = "en"
    lang_dict = TRANSLATIONS.get(lang, TRANSLATIONS.get("en", {}))
    return lang_dict.get(message, message)

def format_file_size(size_bytes: int) -> str:
    """Formats bytes into human-readable KB or MB."""
    if size_bytes < 1024 * 1024:
        return f"{round(size_bytes / 1024, 1)} KB"
    return f"{round(size_bytes / (1024 * 1024), 2)} MB"

def sanitize_filename(filename: str) -> str:
    """Sanitizes filename for safe filesystem persistence."""
    base = os.path.basename(filename)
    cleaned = re.sub(r"[^\w\-.]", "_", base)
    return cleaned or f"file_{secrets.token_hex(4)}"

def get_current_timestamp() -> str:
    """Returns formatted clinical timestamp."""
    return datetime.now().strftime("%Y-%m-%d %I:%M %p")

def generate_patient_id() -> str:
    """Generates unique patient ID token."""
    return f"PAT-{datetime.now().strftime('%M%S')}-{secrets.token_hex(2).upper()}"

# Authentication & Session Helpers
def get_current_user():
    """Retrieves current user from active Flask session or cookies."""
    try:
        from flask import session, request
        from backend.app.database import SessionLocal
        from backend.app.models import User
        
        user_id = session.get("user_id") or request.cookies.get("user_id")
        if not user_id:
            return None
        db = SessionLocal()
        try:
            u = db.query(User).filter(User.id == user_id).first()
            return u.to_dict() if u and u.status.upper() == "ACTIVE" else None
        finally:
            db.close()
    except Exception:
        return None

def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        from flask import redirect, url_for
        u = get_current_user()
        if not u:
            return redirect(url_for("frontend.login_view"))
        return f(*args, **kwargs)
    return decorated

def role_required(*roles):
    def decorator(f):
        @wraps(f)
        def decorated(*args, **kwargs):
            from flask import redirect, url_for
            u = get_current_user()
            if not u:
                return redirect(url_for("frontend.login_view"))
            user_role = u.get("role", "")
            matches = any(r.lower() in user_role.lower() for r in roles)
            if not matches and "Admin" not in user_role:
                return redirect(url_for("frontend.dashboard"))
            return f(*args, **kwargs)
        return decorated
    return decorator
