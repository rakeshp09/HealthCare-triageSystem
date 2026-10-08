"""Entry point for Multimodal AI-Assisted Healthcare Triage Platform.

Mounts FastAPI backend (/api, /docs) and serves Flask frontend (/...)
via asynchronous ASGI WSGI middleware on a single unified server.
"""

import os
from pathlib import Path
from flask import Flask, send_from_directory, session, request
from a2wsgi import WSGIMiddleware
import uvicorn

from config import Config
from backend.app.main import app as fastapi_app
from backend.app.database import init_db
from backend.utils.helpers import load_translations, gettext
from frontend.views import frontend_bp, auth_bp, backend_bp

BASE_DIR = Path(__file__).resolve().parent

def create_flask_app(config_class=Config) -> Flask:
    """Creates and configures the Flask frontend application."""
    frontend_templates = os.path.join(BASE_DIR, "frontend", "templates")
    frontend_static = os.path.join(BASE_DIR, "frontend", "static")

    flask_app = Flask(
        __name__,
        template_folder=frontend_templates,
        static_folder=frontend_static
    )
    flask_app.config.from_object(config_class)

    # Ensure required directories exist
    os.makedirs(flask_app.config["UPLOAD_FOLDER"], exist_ok=True)
    os.makedirs(flask_app.config["DATA_DIR"], exist_ok=True)

    # Initialize translation catalogs
    load_translations(str(BASE_DIR))

    # Register translation helpers in Jinja environment
    flask_app.jinja_env.globals["_"] = gettext
    flask_app.jinja_env.globals["gettext"] = gettext

    @flask_app.context_processor
    def inject_i18n_context():
        lang = session.get("lang", "en")
        return {"current_lang": lang}

    # Register frontend blueprints
    flask_app.register_blueprint(frontend_bp)
    flask_app.register_blueprint(auth_bp)
    flask_app.register_blueprint(backend_bp)

    # Serve uploads
    @flask_app.route("/static/uploads/<filename>")
    @flask_app.route("/uploads/<filename>")
    def uploaded_file(filename):
        return send_from_directory(flask_app.config["UPLOAD_FOLDER"], filename)

    # Serve static assets
    @flask_app.route("/static/js/<path:filename>")
    def serve_static_js(filename):
        js_dir = os.path.join(BASE_DIR, "frontend", "static", "js")
        return send_from_directory(js_dir, filename)

    @flask_app.route("/static/css/<path:filename>")
    def serve_static_css(filename):
        css_dir = os.path.join(BASE_DIR, "frontend", "static", "css")
        return send_from_directory(css_dir, filename)

    return flask_app

# 1. Initialize Database Tables
init_db()

# 2. Create Flask Application
flask_app = create_flask_app()

# 3. Mount Flask Frontend into FastAPI Application as Fallback ASGI Middleware
fastapi_app.mount("/", WSGIMiddleware(flask_app))

# Expose unified application object
app = fastapi_app

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    host = os.environ.get("HOST", "127.0.0.1")
    print("\n" + "=" * 65)
    print(" [+] CLINICAL TRIAGE ASSISTANT PLATFORM v2.0 (FastAPI + RAG)")
    print("=" * 65)
    print(f" Web Application: http://{host}:{port}/")
    print(f" Interactive API Docs: http://{host}:{port}/docs")
    print(f" Alternative API Docs: http://{host}:{port}/redoc")
    print(" Multilingual: English (en) | Hindi (hi) | Odia (or)")
    print(" Role Dashboards: /doctor | /patient | /nurse | /admin")
    print("=" * 65 + "\n")
    uvicorn.run("run:app", host=host, port=port, reload=True)
    
    
    



