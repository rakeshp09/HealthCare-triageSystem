# Healthcare Triage Assistant - Frontend Architecture

## Overview
The frontend is a modular, responsive web interface built using **Flask**, **Jinja2 templates**, **Tailwind CSS**, and **Lucide Icons**, incorporating modern glassmorphism, responsive grid layouts, and multilingual localization catalogs for **English (en)**, **Hindi (hi)**, and **Odia (or)**.

---

## Directory Layout
```
frontend/
├── __init__.py                  # Blueprint exporter
├── views.py                     # UI logic & template router
├── forms.py                     # Client input validation schemas
├── i18n/                        # Localization catalogs (en, hi, or)
│   ├── en/messages.po
│   ├── hi/messages.po
│   └── or/messages.po
├── static/
│   ├── css/style.css            # Tailwind, glassmorphism, badge designs
│   └── js/app.js                # Microphone recording, file upload, modal logic
│   └── js/api_client.js         # Asynchronous REST API helper
└── templates/
    ├── base.html                # Universal navbar, language switcher, profile dropdown
    ├── home.html                # Landing page featuring 6-step architecture & 3 pillars
    ├── login.html               # Authentication with credential autofill
    ├── signup.html              # Role registration (Patient, Nurse, Doctor, Admin)
    ├── patient/
    │   ├── dashboard.html       # Patient EHR portal, vitals logger, diet planner
    │   └── shared_record.html   # Expiring cryptographic record view
    ├── doctor/
    │   └── dashboard.html       # Clinical review queue, IoT vitals telemetry & prescription
    ├── nurse/
    │   └── dashboard.html       # Frontline intake verification & vitals entry
    ├── admin/
    │   └── dashboard.html       # Staff governance & audit trail
    ├── case_detail.html         # Comprehensive case dossier & timeline
    ├── case_review.html         # Physician decision workspace (Reviewed, Escalate, Refer)
    ├── case_handoff.html        # 15-Section Standardized Clinical Handoff Packet
    └── case_referral.html       # Specialist facility routing form
```

---

## Role Portals & Workflows
1. **Patient Portal (`/patient/dashboard`)**: Displays longitudinal health history, self-reporting vitals form, AI nutrition guidance, and temporary record sharing.
2. **Frontline Nurse Intake (`/nurse/dashboard`)**: Triage admission desk where health workers verify patient self-admission requests, record physiological vitals, and approve cases into the doctor queue.
3. **Physician Review Desk (`/doctor/dashboard`)**: Priority-ranked clinical queue, continuous Lead-II ECG and IoT vitals monitoring, prescription issuance, and clinical decision sign-offs.
4. **Clinical Handoff (`/case/<id>/handoff`)**: Generates 15-section handoff dossier ready for immediate print, PDF download, and JSON transfer.
