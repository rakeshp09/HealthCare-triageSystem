# Clinical Protocol: Standardized Emergency Severity Index (ESI) & Frontline Triage

## 1. Scope and Objective
This protocol governs rapid clinical acuity assignment for outpatient, rural health sub-center, and emergency department intakes.

## 2. Five-Level Acuity Classification
- **Level 1 (Resuscitation / Immediate)**: Immediate life threat. Severe respiratory arrest, pulselessness, unresponsiveness, anaphylaxis with airway compromise. Action: Immediate resuscitation bay transfer.
- **Level 2 (Emergent / High Risk)**: High-risk presentation, altered mental status, severe pain/distress, acute chest pain with diaphoresis, acute dyspnea with SpO2 < 90%. Action: Immediate physician evaluation within 10 minutes.
- **Level 3 (Urgent)**: Stable vitals but requiring 2 or more clinical resources (e.g., blood work, radiography, IV medications, nebulization). Action: Evaluation within 30-45 minutes.
- **Level 4 (Semi-Urgent)**: Stable patient requiring 1 diagnostic or therapeutic resource (e.g., simple prescription, suture, single plain X-ray). Action: Evaluation within 60-90 minutes.
- **Level 5 (Non-Urgent)**: Stable patient requiring no additional diagnostic resources (e.g., routine refill, wound re-dressing).

## 3. Mandatory Physiological Vital Sign Thresholds
- **Oxygen Saturation (SpO2)**: Critical if < 92% on room air. Immediate supplemental oxygen therapy and urgent physician escalation required.
- **Respiratory Rate**: Critical if > 30 breaths/min or < 10 breaths/min in adults.
- **Resting Heart Rate**: Severe tachycardia if > 130 bpm; bradycardia if < 45 bpm.
- **Systolic Blood Pressure**: Hypotension if < 90 mmHg; Hypertensive Crisis if >= 180 mmHg or Diastolic >= 110 mmHg with end-organ symptoms.

## 4. Multi-Step Human-in-the-Loop Safeguards
1. Patient self-admissions must be flagged as `PENDING_NURSE_APPROVAL`.
2. Frontline health worker or triage nurse verifies vital signs before admission to physician review queue.
3. Clinician sign-off is mandatory prior to specialist dispatch or referral transfer.
