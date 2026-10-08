"""Clinical Safety Rules Engine and Risk Tagging Service.

Evaluates deterministic clinical safety flags against physiological vitals,
multimodal symptoms, and past medical history with zero halluncination risk.
"""

from typing import Dict, Any, List, Tuple

class SafetyService:
    """Evaluates rule-based safety thresholds and tags clinical risk levels."""

    def evaluate(self, case_data: Dict[str, Any]) -> Tuple[str, List[Dict[str, Any]], List[Dict[str, Any]]]:
        """Evaluates case data and returns (priority, safety_signals, missing_info_tracker)."""
        safety_signals: List[Dict[str, Any]] = []
        missing_info: List[Dict[str, Any]] = []
        
        vitals = case_data.get("vitals") or {}
        history = case_data.get("medicalHistory") or {}
        symptoms_str = (case_data.get("symptoms") or "").lower()
        chief_str = (case_data.get("chiefConcern") or "").lower()
        past_conditions = (history.get("pastConditions") or "").lower()
        combined_text = f"{symptoms_str} {chief_str} {past_conditions}"

        # 1. Oxygen Saturation (SpO2) Rule
        spo2_val = vitals.get("spo2")
        if spo2_val not in (None, "", "null"):
            try:
                spo2_num = float(spo2_val)
                if spo2_num < 92.0:
                    safety_signals.append({
                        "id": f"sig-{len(safety_signals) + 1}",
                        "title": "Critical SpO2 Level Detected",
                        "description": f"Oxygen saturation recorded at {spo2_num}% on room air, falling below standard clinical threshold (92%).",
                        "severity": "CRITICAL" if spo2_num < 90 else "HIGH",
                        "category": "Vital Signs Rule",
                        "source": "Health worker entered vitals"
                    })
                missing_info.append({
                    "field": "SpO2",
                    "originallyPresent": False,
                    "addedByHealthWorker": True,
                    "value": f"{spo2_num}% (Room Air)",
                    "status": "resolved"
                })
            except (ValueError, TypeError):
                pass
        else:
            missing_info.append({
                "field": "SpO2",
                "originallyPresent": False,
                "addedByHealthWorker": False,
                "value": "Pending",
                "status": "missing"
            })

        # 2. Body Temperature Rule (Pyrexia)
        temp_val = vitals.get("temperature")
        hr_val = vitals.get("heartRate")
        if temp_val not in (None, "", "null"):
            try:
                temp_num = float(temp_val)
                hr_num = float(hr_val) if hr_val not in (None, "", "null") else None
                if temp_num >= 39.0:
                    desc = f"Temperature {temp_num}°C indicates high pyrexia."
                    if hr_num and hr_num >= 100:
                        desc += f" Accompanied by resting tachycardia ({int(hr_num)} bpm)."
                    safety_signals.append({
                        "id": f"sig-{len(safety_signals) + 1}",
                        "title": "Persistent High-Grade Pyrexia",
                        "description": desc,
                        "severity": "ELEVATED",
                        "category": "Systemic Flag",
                        "source": "Vitals cross-reference"
                    })
                missing_info.append({
                    "field": "Body Temperature",
                    "originallyPresent": False,
                    "addedByHealthWorker": True,
                    "value": f"{temp_num} °C",
                    "status": "resolved"
                })
            except (ValueError, TypeError):
                pass
        else:
            missing_info.append({
                "field": "Body Temperature",
                "originallyPresent": False,
                "addedByHealthWorker": False,
                "value": "Pending",
                "status": "missing"
            })

        # 3. Blood Pressure Rule (Hypertensive Urgency)
        sys_bp = vitals.get("bloodPressureSys")
        dia_bp = vitals.get("bloodPressureDia")
        if sys_bp not in (None, "", "null") and dia_bp not in (None, "", "null"):
            try:
                sys_num = float(sys_bp)
                dia_num = float(dia_bp)
                if sys_num >= 160 or dia_num >= 100:
                    safety_signals.append({
                        "id": f"sig-{len(safety_signals) + 1}",
                        "title": "Hypertensive Elevation Alert",
                        "description": f"Blood pressure measured at {int(sys_num)}/{int(dia_num)} mmHg.",
                        "severity": "HIGH",
                        "category": "Cardiovascular Flag",
                        "source": "Health worker entered vitals"
                    })
                missing_info.append({
                    "field": "Blood Pressure",
                    "originallyPresent": False,
                    "addedByHealthWorker": True,
                    "value": f"{int(sys_num)}/{int(dia_num)} mmHg",
                    "status": "resolved"
                })
            except (ValueError, TypeError):
                pass
        else:
            missing_info.append({
                "field": "Blood Pressure",
                "originallyPresent": False,
                "addedByHealthWorker": False,
                "value": "Pending",
                "status": "missing"
            })

        # 4. Heart Rate Rule
        if hr_val not in (None, "", "null"):
            try:
                hr_num = float(hr_val)
                if hr_num >= 120 or hr_num <= 50:
                    safety_signals.append({
                        "id": f"sig-{len(safety_signals) + 1}",
                        "title": "Abnormal Heart Rate Alert",
                        "description": f"Resting heart rate measured at {int(hr_num)} bpm.",
                        "severity": "HIGH" if hr_num >= 130 or hr_num <= 45 else "ELEVATED",
                        "category": "Cardiovascular Flag",
                        "source": "Physical vitals check"
                    })
                missing_info.append({
                    "field": "Heart Rate",
                    "originallyPresent": False,
                    "addedByHealthWorker": True,
                    "value": f"{int(hr_num)} bpm",
                    "status": "resolved"
                })
            except (ValueError, TypeError):
                pass
        else:
            missing_info.append({
                "field": "Heart Rate",
                "originallyPresent": False,
                "addedByHealthWorker": False,
                "value": "Pending",
                "status": "missing"
            })

        # 5. Acute Symptoms Red Flags
        if any(term in combined_text for term in ["chest pain", "सीने में दर्द", "pressure in chest", "angina"]):
            safety_signals.append({
                "id": f"sig-{len(safety_signals) + 1}",
                "title": "Acute Chest Discomfort / Angina Flag",
                "description": "Patient reports acute chest pain or pressure radiating symptoms.",
                "severity": "CRITICAL",
                "category": "Cardiovascular Red Flag",
                "source": "Intake narrative analysis"
            })

        if any(term in combined_text for term in ["shortness of breath", "difficulty breathing", "सांस फूलना", "सांस लेने में तकलीफ", "dyspnea", "stridor"]):
            safety_signals.append({
                "id": f"sig-{len(safety_signals) + 1}",
                "title": "Respiratory Distress / Dyspnea Alert",
                "description": "Signs of respiratory compromise identified from patient complaints.",
                "severity": "HIGH",
                "category": "Pulmonary Red Flag",
                "source": "Multimodal intake extraction"
            })

        # 6. Overall Priority Assignment
        priority = "LOW"
        has_critical = any(s.get("severity") == "CRITICAL" for s in safety_signals)
        has_high = any(s.get("severity") == "HIGH" for s in safety_signals)
        has_elevated = any(s.get("severity") == "ELEVATED" for s in safety_signals)

        if has_critical:
            priority = "CRITICAL"
        elif has_high:
            priority = "HIGH"
        elif has_elevated:
            priority = "MEDIUM"
        elif len(safety_signals) > 0:
            priority = "MEDIUM"

        return priority, safety_signals, missing_info

safety_service = SafetyService()
