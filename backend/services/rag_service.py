"""Clinical Retrieval-Augmented Generation (RAG) Service.

Coordinates vector similarity retrieval from ChromaDB and clinical reasoning synthesis
grounded in evidence-based protocols.
"""

import re
from typing import Dict, Any, List, Optional
from ..rag.retriever import rag_retriever
from .llm_service import llm_service
from .safety_service import safety_service
from .extraction_service import extraction_service

REQUIRED_TRIAGE_SCHEMA = {
    "symptoms": {
        "label": "Symptoms & Chief Complaints",
        "type": "text",
        "placeholder": "e.g. High fever, productive cough, breathlessness"
    },
    "temperature": {
        "label": "Body Temperature (°C)",
        "type": "number",
        "placeholder": "e.g. 37.5"
    },
    "spo2": {
        "label": "Oxygen Saturation - SpO2 (%)",
        "type": "number",
        "placeholder": "e.g. 98"
    },
    "blood_pressure": {
        "label": "Blood Pressure (mmHg, e.g. 120/80)",
        "type": "text",
        "placeholder": "e.g. 120/80"
    },
    "heart_rate": {
        "label": "Heart Rate / Pulse (bpm)",
        "type": "number",
        "placeholder": "e.g. 76"
    }
}

class RAGService:
    """Clinical RAG pipeline linking vector retrieval with clinical synthesis."""

    def __init__(self):
        self.retriever = rag_retriever
        self.llm = llm_service
        self.safety = safety_service
        self.extraction = extraction_service

    def analyze_case_with_rag(self, case_data: Dict[str, Any]) -> Dict[str, Any]:
        """Runs RAG retrieval and synthesis on a clinical case."""
        symptoms = case_data.get("symptoms", "")
        concern = case_data.get("chiefConcern", "")
        vitals = case_data.get("vitals", {})

        # 1. Formulate clinical search query
        query = f"Patient presenting with {concern or symptoms}. Vitals: SpO2 {vitals.get('spo2', '--')}, BP {vitals.get('bloodPressureSys', '--')}/{vitals.get('bloodPressureDia', '--')}, Temp {vitals.get('temperature', '--')}."
        
        # 2. Retrieve top relevant protocols
        protocols = self.retriever.retrieve_protocols(query, n_results=3)

        # 3. Deterministic safety evaluation
        priority, safety_signals, missing_info = self.safety.evaluate(case_data)

        # 4. LLM / Heuristic synthesis
        rationale = self.llm.synthesize_triage_rationale(case_data, protocols)

        return {
            "priority": priority,
            "safety_signals": safety_signals,
            "missing_info": missing_info,
            "retrieved_protocols": protocols,
            "clinical_rationale": rationale,
            "citations": [p.get("title") for p in protocols if p.get("title")]
        }

    def extract_entities_and_check_schema(
        self,
        text: str = "",
        report_data: Optional[Dict[str, Any]] = None,
        existing_data: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Extracts available values from clinical narrative or reports and checks against required schema."""
        combined_text = (text or "").strip()
        if report_data:
            findings = report_data.get("findings", "")
            impressions = " ".join(report_data.get("impressions") or [])
            combined_text = f"{combined_text} {findings} {impressions}".strip()

        existing = existing_data or {}
        existing_vitals = existing.get("vitals") or {}

        # 1. Auto-extract structured clinical entities
        structured = self.extraction.extract_structured_json(combined_text)
        extracted_symptoms = structured.get("primary_symptoms", [])
        extracted_conditions = structured.get("conditions", [])
        extracted_duration = structured.get("duration", "Not Reported")
        extracted_concern = structured.get("synthesized_chief_concern", "")

        # 2. Extract vitals from text using clinical regex patterns
        extracted_vitals: Dict[str, Any] = {}

        # Temperature
        temp_match = re.search(
            r"\b(?:temp(?:erature)?|fever|t)[:\s]*([0-9]{2,3}(?:\.[0-9]+)?)\s*(?:°?\s*[cf]|celsius|deg)?\b",
            combined_text,
            re.IGNORECASE
        )
        if temp_match:
            try:
                t_val = float(temp_match.group(1))
                if t_val > 50:
                    t_val = round((t_val - 32) * 5 / 9, 1)
                extracted_vitals["temperature"] = str(t_val)
            except ValueError:
                pass
        elif existing_vitals.get("temperature"):
            extracted_vitals["temperature"] = str(existing_vitals["temperature"])

        # SpO2
        spo2_match = re.search(
            r"\b(?:spo2|o2\s*sat(?:uration)?|oxygen\s*saturation)[:\s]*([0-9]{2,3})\s*%?\b",
            combined_text,
            re.IGNORECASE
        )
        if spo2_match:
            extracted_vitals["spo2"] = spo2_match.group(1)
        elif existing_vitals.get("spo2"):
            extracted_vitals["spo2"] = str(existing_vitals["spo2"])

        # Blood Pressure
        bp_match = re.search(
            r"\b(?:bp|blood\s*pressure)[:\s]*([0-9]{2,3})\s*[/xX\-]\s*([0-9]{2,3})\b",
            combined_text,
            re.IGNORECASE
        )
        if bp_match:
            extracted_vitals["bloodPressureSys"] = bp_match.group(1)
            extracted_vitals["bloodPressureDia"] = bp_match.group(2)
            extracted_vitals["blood_pressure"] = f"{bp_match.group(1)}/{bp_match.group(2)}"
        elif existing_vitals.get("bloodPressureSys") and existing_vitals.get("bloodPressureDia"):
            extracted_vitals["bloodPressureSys"] = str(existing_vitals["bloodPressureSys"])
            extracted_vitals["bloodPressureDia"] = str(existing_vitals["bloodPressureDia"])
            extracted_vitals["blood_pressure"] = f"{existing_vitals['bloodPressureSys']}/{existing_vitals['bloodPressureDia']}"

        # Heart Rate
        hr_match = re.search(
            r"\b(?:hr|pulse|heart\s*rate|pr)[:\s]*([0-9]{2,3})\s*(?:bpm)?\b",
            combined_text,
            re.IGNORECASE
        )
        if hr_match:
            extracted_vitals["heartRate"] = hr_match.group(1)
            extracted_vitals["heart_rate"] = hr_match.group(1)
        elif existing_vitals.get("heartRate"):
            extracted_vitals["heartRate"] = str(existing_vitals["heartRate"])
            extracted_vitals["heart_rate"] = str(existing_vitals["heartRate"])

        # 3. Check extracted JSON keys against required schema
        extracted_keys = set()
        if extracted_symptoms or (existing.get("symptoms") and str(existing["symptoms"]).strip()):
            extracted_keys.add("symptoms")
        if extracted_vitals.get("temperature"):
            extracted_keys.add("temperature")
        if extracted_vitals.get("spo2"):
            extracted_keys.add("spo2")
        if extracted_vitals.get("blood_pressure") or (extracted_vitals.get("bloodPressureSys") and extracted_vitals.get("bloodPressureDia")):
            extracted_keys.add("blood_pressure")
        if extracted_vitals.get("heartRate") or extracted_vitals.get("heart_rate"):
            extracted_keys.add("heart_rate")

        missing_fields = [k for k in REQUIRED_TRIAGE_SCHEMA.keys() if k not in extracted_keys]
        missing_fields_details = [{"field": k, **REQUIRED_TRIAGE_SCHEMA[k]} for k in missing_fields]

        # 4. RAG Protocol Retrieval for clinical context
        search_query = f"Patient presentation: {', '.join(extracted_symptoms) if extracted_symptoms else combined_text[:120]}"
        retrieved_protocols = self.retriever.retrieve_protocols(search_query, n_results=3)

        return {
            "success": True,
            "extracted_entities": {
                "symptoms": extracted_symptoms,
                "duration": extracted_duration,
                "conditions": extracted_conditions,
                "synthesized_chief_concern": extracted_concern,
                "vitals": extracted_vitals,
                "raw_findings": combined_text
            },
            "extracted_keys": list(extracted_keys),
            "missing_fields": missing_fields,
            "missing_fields_details": missing_fields_details,
            "retrieved_protocols": retrieved_protocols,
            "message": (
                f"Auto-extracted available entities. {len(missing_fields)} required fields missing: {', '.join(missing_fields)}."
                if missing_fields else "All required clinical fields extracted successfully."
            )
        }

rag_service = RAGService()
