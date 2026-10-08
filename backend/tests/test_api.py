"""Unit and Integration Test Suite for Healthcare Triage Backend.
"""

import unittest
from fastapi.testclient import TestClient
from backend.app.main import app
from backend.services.safety_service import safety_service
from backend.rag.retriever import rag_retriever
from backend.app.reports import assemble_15_section_dossier
from run import flask_app

class TestHealthcareAPI(unittest.TestCase):
    """Test suite for FastAPI endpoints and clinical services."""

    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(app)

    def test_health_check(self):
        """Tests health check endpoint."""
        resp = self.client.get("/api/health")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["status"], "healthy")

    def test_safety_rules_critical_spo2(self):
        """Verifies deterministic clinical safety rule for SpO2 < 92%."""
        case_data = {
            "vitals": {"spo2": 88, "temperature": 37.0, "bloodPressureSys": 120, "bloodPressureDia": 80},
            "symptoms": "Mild cough",
            "medicalHistory": {}
        }
        priority, signals, missing = safety_service.evaluate(case_data)
        self.assertEqual(priority, "CRITICAL")
        self.assertTrue(any("SpO2" in s["title"] for s in signals))

    def test_safety_rules_hypertension(self):
        """Verifies hypertensive alert when Systolic BP >= 160."""
        case_data = {
            "vitals": {"spo2": 97, "temperature": 37.0, "bloodPressureSys": 165, "bloodPressureDia": 105},
            "symptoms": "Headache",
            "medicalHistory": {}
        }
        priority, signals, missing = safety_service.evaluate(case_data)
        self.assertEqual(priority, "HIGH")
        self.assertTrue(any("Hypertensive" in s["title"] for s in signals))

    def test_rag_protocol_retrieval(self):
        """Tests RAG retrieval for respiratory distress query."""
        results = rag_retriever.retrieve_protocols("acute asthma wheezing dyspnea", n_results=2)
        self.assertIsInstance(results, list)
        if len(results) > 0:
            self.assertIn("title", results[0])

    def test_15_section_dossier_assembly(self):
        """Tests that the standardized handoff dossier contains all 15 required sections."""
        mock_case = {
            "patientId": "TEST-PAT-01",
            "age": 45,
            "gender": "Female",
            "language": "Hindi",
            "symptoms": "High fever and cough",
            "vitals": {"spo2": 96, "temperature": 38.5}
        }
        dossier = assemble_15_section_dossier(mock_case)
        self.assertEqual(len(dossier), 15)
        self.assertIn("section_1_patient_demographics", dossier)
        self.assertIn("section_4_physical_vitals", dossier)
        self.assertIn("section_9_advisory_safety_signals", dossier)
        self.assertIn("section_15_system_version", dossier)

    def test_get_cases_endpoint(self):
        """Tests fetching cases from API."""
        resp = self.client.get("/api/cases")
        self.assertEqual(resp.status_code, 200)
        self.assertIsInstance(resp.json(), list)

    def test_frontend_logout_route_redirects(self):
        """Verifies the frontend logout route is registered and does not 404."""
        resp = flask_app.test_client().get("/logout", follow_redirects=False)
        self.assertIn(resp.status_code, (302, 303))

    def test_zero_hallucination_entity_extraction(self):
        """Verifies that unmentioned medical entities are never hallucinated."""
        from backend.services.extraction_service import extraction_service

        raw_narrative = "Patient reports mild cough and headache."
        structured = extraction_service.extract_structured_json(raw_narrative, history_dict={})

        self.assertIn("Cough", str(structured["primary_symptoms"]))
        self.assertEqual(structured["duration"], "Not Reported")
        self.assertEqual(structured["conditions"], [])
        self.assertEqual(structured["allergies"], [])
        self.assertEqual(structured["current_medications"], [])

        # Ensure no placeholder values exist
        self.assertNotIn("Bronchial Asthma", structured["conditions"])
        self.assertNotIn("Penicillin", structured["allergies"])
        self.assertNotEqual(structured["duration"], "3 days")

        # Full case entity extraction check
        extracted_case = extraction_service.extract_entities({
            "symptoms": raw_narrative,
            "medicalHistory": {}
        })
        self.assertIsNone(extracted_case["vitals"])
        self.assertEqual(extracted_case["conditions"], [])
        self.assertEqual(extracted_case["allergies"], [])
        self.assertEqual(extracted_case["current_medications"], [])
        self.assertEqual(extracted_case["duration"], "Not Reported")

    def test_zero_hallucination_with_explicit_evidence(self):
        """Verifies that explicit conditions and durations are accurately extracted."""
        from backend.services.extraction_service import extraction_service

        text = "Patient diagnosed with asthma presents with fever and cough for 5 days."
        structured = extraction_service.extract_structured_json(text, history_dict={})

        self.assertIn("Bronchial Asthma", structured["conditions"])
        self.assertIn("5 days", structured["duration"])
        self.assertEqual(structured["allergies"], [])
        self.assertEqual(structured["current_medications"], [])

    def test_nurse_admission_approval_success(self):
        """Verifies nurse admission approval transitions status to READY_FOR_REVIEW with HTTP 200."""
        # 1. Create a case in PENDING_NURSE_APPROVAL
        case_id = "TEST-NURSE-PAT01"
        create_payload = {
            "patientId": case_id,
            "age": 30,
            "gender": "Female",
            "language": "Hindi",
            "symptoms": "High fever for 2 days",
            "status": "PENDING_NURSE_APPROVAL"
        }
        res_create = self.client.post("/api/cases", json=create_payload)
        self.assertIn(res_create.status_code, (200, 201))

        # 2. Approve admission with verified vitals
        approval_payload = {
            "vitals": {
                "temperature": "38.2",
                "spo2": "97",
                "heartRate": "84"
            }
        }
        res_approve = self.client.post(f"/api/cases/{case_id}/approve-admission", json=approval_payload)
        self.assertEqual(res_approve.status_code, 200)

        data = res_approve.json()
        self.assertEqual(data["status"], "success")
        self.assertEqual(data["message"], "Case admission approved successfully")
        self.assertEqual(data["caseData"]["status"], "READY_FOR_REVIEW")
        self.assertEqual(data["caseData"]["vitals"]["temperature"], "38.2")
        self.assertEqual(data["caseData"]["vitals"]["spo2"], "97")

        # 3. Test alias route /api/cases/{case_id}/approve
        res_alias = self.client.post(f"/api/cases/{case_id}/approve", json={"vitals": {"spo2": "98"}})
        self.assertEqual(res_alias.status_code, 200)
        alias_data = res_alias.json()
        self.assertEqual(alias_data["status"], "success")
        self.assertEqual(alias_data["caseData"]["status"], "READY_FOR_REVIEW")

    def test_flask_fallback_admission_approval(self):
        """Verifies Flask fallback admission approval endpoint returns HTTP 200 with success."""
        case_id = "TEST-NURSE-PAT01"
        res = flask_app.test_client().post(
            f"/cases/{case_id}/approve-admission",
            json={"vitals": {"temperature": "37.5", "spo2": "99"}},
            headers={"Content-Type": "application/json"}
        )
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertEqual(data["status"], "success")
        self.assertEqual(data["message"], "Case admission approved successfully")

if __name__ == "__main__":
    unittest.main()
