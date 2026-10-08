# Multimodal AI-Assisted Healthcare Triage & Handoff Platform (Python Flask)

> **Tagline**: *"From Patient Voice to Doctor-Ready Information"*  
> **Environment**: Python 3.10+ / Flask / FastAPI / PostgreSQL / Tailwind CSS  
> **Prototype Environment**: Synthetic / Demo Patient Data Only

---

## ⚕️ Important Clinical Safety Principle

This application is an **AI-assisted healthcare triage and clinical information-handoff platform**.  
- It **DOES NOT** claim to diagnose diseases, prescribe medications, or replace healthcare practitioners.
- AI transcribes multilingual voice, structures clinical entities, detects missing parameters, and identifies rule-based safety flags.
- **A qualified human medical professional makes the final clinical decision.**

---

## 🚀 Key Features

1. **Multimodal Intake & Audio Support**:
   - **Live Voice Recording**: In-browser microphone audio recording with real-time timer and playback.
   - **Audio File Upload**: Upload patient audio notes (.wav, .mp3, .ogg, .webm) processed directly by `stt_module.py`.
   - **Speech-to-Text Pipeline**: Multilingual transcription and clinical chief concern extraction across 6 Indian languages.
   - **Text & Reports**: Clinical symptom narrative input, high-resolution Chest X-Rays, and lab reports (JPG, PNG, PDF).
   - **Vitals**: Physiological measurements (SpO2, Body Temp, BP, Heart Rate).

2. **Multi-Stage Patient Admission Protocol**:
   - **Self-Admission Guardrail**: Patients can only admit themselves (cannot admit others).
   - **Nurse Verification Gateway**: Self-admissions enter `PENDING_NURSE_APPROVAL` and require nurse vital check/approval before reaching the doctor queue.
   - **Doctor Triage**: Once approved by nursing staff (`READY_FOR_REVIEW`), physicians conduct clinical reviews, adjust AI extractions, or generate specialist referrals.

3. **Multilingual Speech & Text**:
   - Tailored for Indian public healthcare settings (Hindi, Odia, Bengali, Tamil, Telugu, English).

4. **Human-in-the-Loop & Transparent Source Attribution**:
   - Explicit provenance tags: `PATIENT-REPORTED`, `HEALTH-WORKER ENTERED`, `AI-EXTRACTED`, `SYSTEM SAFETY FLAG`, `DOCTOR/REVIEWER DECISION`.

5. **15-Section Standardized Clinical Handoff Packet**:
   - Standardized clinical dossier formatted for immediate print/PDF export, JSON export (`PAT-002_case.json`), and verbatim transcript export (`PAT-002_transcript.txt`).

6. **Role-Adaptive Workspaces**:
   - **Frontline Health Worker / Nurse**: Patient registration, consent confirmation, admission verification, vitals entry, send to doctor.
   - **Doctor / Reviewer**: Clinical queue, comprehensive dossier inspection, editable AI extractions, escalation, referral creation, final decision sign-off.
   - **Administrator**: System throughput, staff account approvals, audit trail tracking, and status monitoring.
   - **Patient**: Personal consultation dossier, self-admission submission, and review status tracker.

---

## 📁 Project Structure

```
project-root/
│
├── frontend/
│   ├── __init__.py
│   ├── views.py              # Public UI logic & template router
│   ├── forms.py              # Input forms & validation
│   ├── i18n/                 # Localization catalogs (en, hi, or)
│   ├── static/
│   │   ├── css/
│   │   │   └── style.css     # Modern responsive design, glassmorphism, animations
│   │   └── js/
│   │       └── app.js        # Voice recorder, report viewer, modal logic
│   └── templates/
│       ├── base.html         # Base template with Tailwind & Lucide icons
│       ├── home.html         # Landing page (ClinicWala-inspired, Telecare, Franchise)
│       ├── about.html        # Clinical safety principle & mission
│       ├── contact.html      # Facility directory & inquiry form
│       ├── testimonials.html # Verified patient & provider stories
│       ├── login.html        # Authentication with 1-click test fill
│       ├── signup.html       # Role registration with admin approval logic
│       ├── case_directory.html # Filterable case registry
│       ├── new_case_wizard.html # 5-step interactive intake wizard
│       ├── case_detail.html  # Patient case dossier
│       ├── case_review.html  # Doctor clinical review & extraction editor
│       ├── case_handoff.html # 15-section standardized clinical handoff packet
│       ├── case_referral.html # Specialist referral routing
│       ├── doctor/
│       │   └── dashboard.html # Clinical review queue & triage desk
│       ├── patient/
│       │   ├── dashboard.html # Patient consultation portal & EHR tracker
│       │   └── shared_record.html # Secure expiring public dossier view
│       ├── nurse/
│       │   └── dashboard.html # Frontline intake & vitals verification desk
│       └── admin/
│           └── dashboard.html # Staff governance, audit trail, user status control
│
├── backend/
│   ├── __init__.py
│   ├── models/               # SQLAlchemy ORM Data Layer
│   │   ├── base.py           # Shared SQLAlchemy db instance
│   │   ├── user.py           # User accounts & PBKDF2-SHA512 hashing
│   │   ├── ehr.py            # Electronic Health Records & cases
│   │   └── testimonial.py    # Community reviews & ratings
│   ├── routes/               # Modular Blueprint Routes
│   │   ├── auth.py           # Login, registration, session management
│   │   ├── doctor.py         # Physician review & sign-off endpoints
│   │   ├── nurse.py          # Frontline admission & triage intake
│   │   ├── patient.py        # Patient EHR, vitals telemetry, share links
│   │   ├── admin.py          # Admin approvals & audit log views
│   │   └── api.py            # JSON REST APIs
│   ├── services/             # Clinical AI Services
│   │   └── transformers_service.py # AI clinical diet & nutritional engine
│   └── utils/
│       └── helpers.py        # Authentication decorators & helpers
│
├── workflow/
│   ├── __init__.py
│   ├── pipeline.py           # Master pipeline orchestrator
│   ├── ocr_module.py         # Diagnostic report OCR parser
│   ├── stt_module.py         # Speech-to-text & clinical chief concern formatter
│   ├── risk_tagging.py       # Clinical safety rule engine & vital sign threshold tagging
│   ├── queue_manager.py      # State machine & queue priority manager
│   └── referral_prep.py      # 15-section handoff dossier & referral generator
│
├── config.py                 # Configuration settings (DB URI, secret key)
├── run.py                    # Flask application entry point
├── requirements.txt          # Python dependencies
└── README.md
```

---

## 🛠️ Prerequisites & Installation

### 1. Requirements
- **Python**: v3.10+ (tested on Python 3.13)
- **pip**: v22+

### 2. Install Dependencies
```bash
pip install -r requirements.txt
```

### 3. Start the Application
```bash
python run.py
```
Open **[http://127.0.0.1:5000](http://127.0.0.1:5000)** in your browser.

---

## Default Accounts

- Patient → username: patient01 | password: patient@123
- Health Worker → username: healthworker01 | password: health@123
- Doctor → username: doctor01 | password: doctor@123
- Admin → username: admin01 | password: admin@123

> **Notice**: These default accounts are sample credentials configured for testing, evaluation, and demonstration purposes only.  
> **Note: Change or disable these accounts before production deployment.**

### Account Roles and Access Permissions

| Role | Username | Password | Access / Permitted Workflows |
|------|----------|----------|------------------------------|
| **Patient** | `patient01` | `patient@123` | Patient consultation portal, self-admission submission, longitudinal EHR, vital logs, secure shareable link generation |
| **Health Worker** | `healthworker01` | `health@123` | Frontline intake desk, vitals recording, pending self-admission review and approval to doctor queue |
| **Doctor** | `doctor01` | `doctor@123` | Clinical review queue, AI entity extraction adjustment, risk tag validation, 15-section handoff generation, specialist referral sign-off |
| **Admin** | `admin01` | `admin@123` | System oversight, user account approval/status governance, clinical audit log inspection |

---