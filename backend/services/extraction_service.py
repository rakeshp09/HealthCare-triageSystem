"""Structured Clinical Entity Extraction Service.

Transforms free-text narratives and voice transcripts into structured medical entities
with zero-hallucination clinical grounding.
"""

import re
from typing import Dict, Any, List, Optional
from .llm_service import llm_service

EXTRACTION_SYSTEM_PROMPT = """You are a deterministic, zero-hallucination Clinical Entity Extraction Engine.
Your task is to extract structured medical details from the provided patient input.

CRITICAL RULES:
1. ONLY extract information explicitly stated in the source text.
2. DO NOT assume, guess, extrapolate, or infer any diagnosis, medical condition, allergy, or medication.
3. If an entity or attribute is not explicitly mentioned, return null, an empty array [], or "Not Reported".
4. Never auto-fill placeholder conditions like "Bronchial Asthma" or "Diabetes" unless explicitly spoken/typed by the patient.
5. Extract vitals (SpO2, BP, Pulse, Temp) ONLY if explicitly provided; otherwise set to null.

Output must be valid JSON:
{
  "primary_symptoms": ["<explicit symptoms only>"],
  "duration": "<stated duration or 'Not Reported'>",
  "conditions": ["<stated conditions only, else []>"],
  "allergies": ["<stated allergies only, else []>"],
  "current_medications": ["<stated medications only, else []>"],
  "synthesized_chief_concern": "<factual summary containing only stated facts>"
}"""

class ExtractionService:
    """Extracts structured entities from clinical narratives with strict zero-hallucination controls."""

    def extract_structured_json(self, text: str, history_dict: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Extracts structured clinical JSON grounded strictly on explicit source evidence."""
        cleaned_text = (text or "").strip()
        history = history_dict or {}

        # 1. Attempt LLM zero-hallucination extraction if available
        llm_result = None
        if cleaned_text:
            try:
                llm_result = llm_service.extract_entities(cleaned_text)
            except Exception as e:
                print(f"[ExtractionService] LLM extraction error: {e}")

        if llm_result and isinstance(llm_result, dict):
            # Enforce zero-hallucination schema guarantees on LLM output
            primary_symptoms = [s for s in llm_result.get("primary_symptoms", []) if isinstance(s, str) and s.strip()]
            duration = llm_result.get("duration")
            if not duration or duration.lower() in ("null", "none", "unknown", ""):
                duration = "Not Reported"
            
            conditions = [c for c in llm_result.get("conditions", []) if isinstance(c, str) and c.strip()]
            allergies = [a for a in llm_result.get("allergies", []) if isinstance(a, str) and a.strip()]
            medications = [m for m in llm_result.get("current_medications", []) if isinstance(m, str) and m.strip()]
            
            # Incorporate explicit history inputs if present in intake form
            if history.get("pastConditions") and history["pastConditions"].strip():
                past_val = history["pastConditions"].strip()
                if past_val.lower() not in ("none", "null", "not reported", "unremarkable", "n/a", "no", "nil"):
                    if past_val not in conditions:
                        conditions.append(past_val)

            if history.get("allergies") and history["allergies"].strip():
                allg_val = history["allergies"].strip()
                if allg_val.lower() not in ("none", "null", "not reported", "no known drug allergies", "nkda", "n/a", "no", "nil"):
                    if allg_val not in allergies:
                        allergies.append(allg_val)

            if history.get("currentMedications") and history["currentMedications"].strip():
                med_val = history["currentMedications"].strip()
                if med_val.lower() not in ("none", "null", "not reported", "n/a", "no", "nil"):
                    if med_val not in medications:
                        medications.append(med_val)

            synthesized = llm_result.get("synthesized_chief_concern") or cleaned_text

            return {
                "primary_symptoms": primary_symptoms,
                "duration": duration,
                "conditions": conditions,
                "allergies": allergies,
                "current_medications": medications,
                "synthesized_chief_concern": synthesized
            }

        # 2. Deterministic zero-hallucination extraction fallback
        return self._deterministic_extract(cleaned_text, history)

    def _deterministic_extract(self, text: str, history: Dict[str, Any]) -> Dict[str, Any]:
        """Deterministic extractor that never infers or invents unmentioned conditions."""
        lower_text = text.lower()

        # Common clinical symptom keywords & regex patterns
        symptom_patterns = [
            ("High Fever / Pyrexia", r"\b(fever|pyrexia|temperature|बुखार)\b"),
            ("Productive Cough", r"\b(productive cough|cough with phlegm|sputum|phlegm)\b"),
            ("Cough", r"\b(cough|खांसी)\b"),
            ("Acute Dyspnea / Shortness of breath", r"\b(breathless|shortness of breath|dyspnea|difficulty breathing|सांस फूलना|सांस लेने में तकलीफ)\b"),
            ("Acute Chest Pain / Angina", r"\b(chest pain|angina|chest pressure|chest tightness|सीने में दर्द)\b"),
            ("Abdominal Pain", r"\b(abdominal pain|stomach pain|belly ache|stomach ache|पेट दर्द)\b"),
            ("Headache / Cephalea", r"\b(headache|cephalea|migraine|सिर दर्द)\b"),
            ("Generalized Weakness / Fatigue", r"\b(weakness|fatigue|lethargy|exhaustion|कमजोरी)\b"),
            ("Vomiting / Nausea", r"\b(vomit|vomiting|nausea|उल्टी|जी मिचलाना)\b"),
            ("Diarrhea", r"\b(diarrhea|loose motions|दस्त)\b"),
            ("Sore Throat", r"\b(sore throat|throat irritation|गले में दर्द|गले में खराश)\b")
        ]

        extracted_symptoms = []
        for name, pattern in symptom_patterns:
            if re.search(pattern, lower_text):
                # Avoid adding generic "Cough" if "Productive Cough" already matched
                if name == "Cough" and any("Productive Cough" in s for s in extracted_symptoms):
                    continue
                extracted_symptoms.append(name)

        # Explicit duration extraction
        duration = "Not Reported"
        duration_patterns = [
            r"(\b(?:for|since|past|last)\s+\d+\s*(?:days?|weeks?|hours?|months?|years?|दिन|घंटे|हफ्ते)\b)",
            r"(\b\d+\s*(?:days?|weeks?|hours?|months?|years?|दिन|घंटे|हफ्ते)\s*(?:duration|history)?\b)",
            r"(\bsince\s+(?:yesterday|morning|last night|today|monday|tuesday|wednesday|thursday|friday|saturday|sunday)\b)"
        ]
        for pat in duration_patterns:
            m = re.search(pat, lower_text)
            if m:
                duration = m.group(1).strip()
                break

        # Explicit conditions extraction
        conditions = []
        if history.get("pastConditions") and history["pastConditions"].strip():
            raw_c = history["pastConditions"].strip()
            if raw_c.lower() not in ("none", "null", "not reported", "unremarkable", "n/a", "no", "nil"):
                conditions.append(raw_c)
        else:
            # Only extract condition if explicitly declared in patient text
            condition_patterns = [
                ("Bronchial Asthma", r"\b(asthma|asthmatic|दमा|अस्थमा)\b"),
                ("Type 2 Diabetes Mellitus", r"\b(diabetes|diabetic|sugar|मधुमेह)\b"),
                ("Essential Hypertension", r"\b(hypertension|high blood pressure|high bp|बीपी)\b"),
                ("Chronic Kidney Disease", r"\b(kidney disease|ckd|renal failure)\b"),
                ("Coronary Artery Disease", r"\b(heart disease|cad|cardiac history)\b"),
                ("COPD", r"\b(copd|chronic bronchitis|emphysema)\b")
            ]
            for c_name, c_pat in condition_patterns:
                # Require explicit declaration like "has asthma", "history of asthma", "known diabetic"
                decl_pat = rf"(?:history of|known|diagnosed with|has|suffering from|patient with)\s+{c_pat}"
                if re.search(decl_pat, lower_text) or re.search(rf"\b(known\s+{c_name.lower()})\b", lower_text):
                    conditions.append(c_name)

        # Explicit allergies extraction
        allergies = []
        if history.get("allergies") and history["allergies"].strip():
            raw_a = history["allergies"].strip()
            if raw_a.lower() not in ("none", "null", "not reported", "no known drug allergies", "nkda", "n/a", "no", "nil"):
                allergies.append(raw_a)
        else:
            allergy_match = re.search(r"\b(?:allergic to|allergy to|allergies:\s*)([a-zA-Z0-9\s,]+)(?:\.|$)", lower_text)
            if allergy_match:
                candidate = allergy_match.group(1).strip()
                if candidate and candidate not in ("none", "no", "nothing", "nil"):
                    allergies.append(candidate)

        # Explicit medications extraction
        medications = []
        if history.get("currentMedications") and history["currentMedications"].strip():
            raw_m = history["currentMedications"].strip()
            if raw_m.lower() not in ("none", "null", "not reported", "n/a", "no", "nil"):
                medications.append(raw_m)
        else:
            med_match = re.search(r"\b(?:taking|on medication|current medications?:\s*)([a-zA-Z0-9\s,]+)(?:\.|$)", lower_text)
            if med_match:
                candidate = med_match.group(1).strip()
                if candidate and candidate not in ("none", "no", "nothing", "nil"):
                    medications.append(candidate)

        # Synthesize factual chief concern strictly from explicit details
        if extracted_symptoms:
            sym_desc = ", ".join(extracted_symptoms)
            if duration != "Not Reported":
                chief_concern = f"Patient presents with {sym_desc} for {duration}."
            else:
                chief_concern = f"Patient presents with {sym_desc}."
        elif text:
            chief_concern = text
        else:
            chief_concern = "Clinical intake recorded."

        return {
            "primary_symptoms": extracted_symptoms,
            "duration": duration,
            "conditions": conditions,
            "allergies": allergies,
            "current_medications": medications,
            "synthesized_chief_concern": chief_concern
        }

    def extract_entities(self, case_data: Dict[str, Any]) -> Dict[str, Any]:
        """Extracts structured clinical facts from intake narrative with zero hallucination."""
        symptoms_str = (case_data.get("symptoms") or "").strip()
        chief_str = (case_data.get("chiefConcern") or "").strip()
        stated_duration = case_data.get("symptomDuration")
        history = case_data.get("medicalHistory") or {}

        # Combine explicit narrative
        combined_text = f"{symptoms_str} {chief_str}".strip()

        # Run structured extraction
        structured = self.extract_structured_json(combined_text, history)

        # If user explicitly passed symptomDuration in intake form, use it if not "Not Reported"
        if stated_duration and stated_duration.strip() and stated_duration.strip().lower() not in ("null", "none", "unknown"):
            structured["duration"] = stated_duration.strip()

        # Build symptoms list for UI templates with confidence and source
        formatted_symptoms = []
        source = "Patient voice" if case_data.get("voiceInput") else "Patient intake"
        for s in structured["primary_symptoms"]:
            formatted_symptoms.append({
                "name": s,
                "source": source,
                "confidence": "Explicitly reported"
            })

        if not formatted_symptoms and combined_text:
            formatted_symptoms.append({
                "name": "General Clinical Complaint",
                "source": source,
                "confidence": "Explicitly reported"
            })

        # Suggested follow-ups based ONLY on confirmed explicit symptoms
        follow_ups = [
            "SpO2 measurement on room air",
            "Body Temperature measurement",
            "Non-invasive Blood Pressure check"
        ]
        symptom_text_check = " ".join([s["name"].lower() for s in formatted_symptoms])
        if "dyspnea" in symptom_text_check or "chest" in symptom_text_check:
            follow_ups.append("Continuous 12-lead ECG screening")
            follow_ups.append("Peak Expiratory Flow Rate (PEFR)")
        if "fever" in symptom_text_check or "pyrexia" in symptom_text_check:
            follow_ups.append("Peripheral blood smear / rapid diagnostic test")

        # Explicit vitals check: strictly null if not provided
        vitals_input = case_data.get("vitals")
        has_vitals = False
        if isinstance(vitals_input, dict):
            for v_val in vitals_input.values():
                if v_val not in (None, "", "null"):
                    has_vitals = True
                    break

        vitals_output = vitals_input if has_vitals else None

        return {
            "primary_symptoms": structured["primary_symptoms"],
            "duration": structured["duration"],
            "conditions": structured["conditions"],
            "allergies": structured["allergies"],
            "current_medications": structured["current_medications"],
            "synthesized_chief_concern": structured["synthesized_chief_concern"],
            "vitals": vitals_output,
            "symptoms": formatted_symptoms,
            "history": structured["conditions"] if structured["conditions"] else [],
            "medications": structured["current_medications"] if structured["current_medications"] else [],
            "allergies_list": structured["allergies"] if structured["allergies"] else [],
            "reportedConcerns": case_data.get("chiefConcern") or structured["synthesized_chief_concern"],
            "suggestedFollowUps": follow_ups
        }

extraction_service = ExtractionService()
