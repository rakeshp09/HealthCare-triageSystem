import sys
import os
import unittest
from datetime import datetime

# Add root directory to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from run import flask_app as app
from backend.app.database import SessionLocal
from backend.app.models import User, Case, ElectronicHealthRecord
from backend.app.security import hash_password

class TestClinicWalaFrontend(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        app.config["TESTING"] = True
        cls.client = app.test_client()

        # Seed test patient, doctor, and nurse users
        db = SessionLocal()
        try:
            creds = hash_password("Password123!")
            now = datetime.now().strftime("%Y-%m-%d %I:%M %p")
            
            # Patient
            if not db.query(User).filter_by(username="test_patient_cw").first():
                p_user = User(
                    id="usr_patient_cw",
                    name="Rajesh Sharma",
                    username="test_patient_cw",
                    email="rajesh@example.com",
                    password_hash=creds["hash"],
                    salt=creds["salt"],
                    role="Patient",
                    status="ACTIVE",
                    created_at=now,
                    updated_at=now
                )
                db.add(p_user)
                ehr = ElectronicHealthRecord(
                    id="ehr_patient_cw",
                    patient_id="test_patient_cw",
                    vitals={"spo2": 98, "heartRate": 74, "bloodPressureSys": 120, "bloodPressureDia": 80},
                    prescriptions=[{"medication": "Amoxicillin 500mg", "dosage": "1 cap tid", "frequency": "TID", "duration": "5 days", "prescribed_by": "Dr. Mahapatra"}],
                    reports=[{"id": "rep-test", "fileType": "Blood Complete Count", "findings": "Within normal limits", "url": "/static/uploads/cbc.pdf"}]
                )
                db.add(ehr)

            # Doctor
            if not db.query(User).filter_by(username="test_doctor_cw").first():
                d_user = User(
                    id="usr_doctor_cw",
                    name="Anita Roy",
                    username="test_doctor_cw",
                    email="anita@example.com",
                    password_hash=creds["hash"],
                    salt=creds["salt"],
                    role="Doctor",
                    status="ACTIVE",
                    created_at=now,
                    updated_at=now
                )
                db.add(d_user)

            # Nurse / Health Worker
            if not db.query(User).filter_by(username="test_nurse_cw").first():
                n_user = User(
                    id="usr_nurse_cw",
                    name="Pooja Verma",
                    username="test_nurse_cw",
                    email="pooja@example.com",
                    password_hash=creds["hash"],
                    salt=creds["salt"],
                    role="Health Worker",
                    status="ACTIVE",
                    created_at=now,
                    updated_at=now
                )
                db.add(n_user)

            # Test Case
            if not db.query(Case).filter_by(id="case_cw_test1").first():
                test_case = Case(
                    id="case_cw_test1",
                    patient_id="P-CW-101",
                    status="READY_FOR_REVIEW",
                    priority="HIGH",
                    language="English",
                    data={
                        "id": "case_cw_test1",
                        "patientId": "P-CW-101",
                        "chiefConcern": "Fever, acute cough and mild dyspnea for 3 days",
                        "status": "READY_FOR_REVIEW",
                        "priority": "HIGH",
                        "language": "English",
                        "createdAt": now,
                        "vitals": {"spo2": 94, "heartRate": 88, "bloodPressureSys": 130, "bloodPressureDia": 85},
                        "auditTrail": []
                    },
                    created_at=now,
                    updated_at=now
                )
                db.add(test_case)

            db.commit()
        finally:
            db.close()

    def test_01_public_and_auth_pages_render(self):
        """Test registration, login, and home page rendering with navbar and footer."""
        res_signup = self.client.get("/signup")
        self.assertEqual(res_signup.status_code, 200)
        self.assertIn(b"Create Account", res_signup.data)
        self.assertIn(b"Salutation", res_signup.data)
        self.assertIn(b"Date of Birth", res_signup.data)
        self.assertIn(b"Guardian Relation", res_signup.data)
        self.assertIn(b"#002B5B", res_signup.data)
        self.assertIn(b"Privacy Policy", res_signup.data)

        # Check that MedAI chatbot button is removed completely
        self.assertNotIn(b"medAiFloatingBtn", res_signup.data)
        self.assertNotIn(b"MedAI", res_signup.data)

        res_login = self.client.get("/login")
        self.assertEqual(res_login.status_code, 200)
        self.assertNotIn(b"medAiFloatingBtn", res_login.data)

    def test_02_registration_api_with_new_fields(self):
        """Test registration form submission with clean English fields."""
        payload = {
            "salutation": "Mrs",
            "name": "Sunita Devi",
            "dob": "1992-06-15",
            "gender": "Female",
            "guardian_relation": "W/O",
            "guardian_name": "Ramesh Devi",
            "email": "sunita@example.com",
            "role": "Patient",
            "password": "Password123!",
            "confirm_password": "Password123!"
        }
        res = self.client.post("/signup", json=payload, headers={"Accept": "application/json"})
        self.assertEqual(res.status_code, 201)
        data = res.get_json()
        self.assertTrue(data.get("success"))
        self.assertEqual(data.get("message"), "Account created successfully")

    def test_03_registration_password_mismatch(self):
        """Test registration fails cleanly when passwords don't match."""
        payload = {
            "name": "Mismatched User",
            "password": "Password123!",
            "confirm_password": "WrongPassword999!"
        }
        res = self.client.post("/signup", json=payload, headers={"Accept": "application/json"})
        self.assertEqual(res.status_code, 400)
        data = res.get_json()
        self.assertFalse(data.get("success"))
        self.assertIn("match", data.get("message").lower())

    def test_04_patient_dashboard(self):
        """Test patient dashboard renders with Good evening greeting, sidebar, serial cards, and activity."""
        with self.client.session_transaction() as sess:
            sess["user_id"] = "usr_patient_cw"
        
        res = self.client.get("/patient/dashboard")
        self.assertEqual(res.status_code, 200)
        # Check greeting format
        self.assertIn(b"Good evening, Rajesh Sharma", res.data)
        # Check sidebar links
        self.assertIn(b"Dashboard", res.data)
        self.assertIn(b"Case Management", res.data)
        self.assertIn(b"Referrals", res.data)
        self.assertIn(b"Health Records", res.data)
        self.assertIn(b"Profile", res.data)
        # Check serial cards
        self.assertIn(b"Health Records", res.data)
        self.assertIn(b"Active Cases", res.data)
        self.assertIn(b"My Activity", res.data)
        # Confirm chatbot button is removed
        self.assertNotIn(b"medAiFloatingBtn", res.data)
        self.assertNotIn(b"MedAI", res.data)

    def test_05_doctor_dashboard(self):
        """Test doctor dashboard with Good evening greeting, patient records, inline delete button, and exact confirmation prompt."""
        with self.client.session_transaction() as sess:
            sess["user_id"] = "usr_doctor_cw"

        res = self.client.get("/doctor/dashboard")
        self.assertEqual(res.status_code, 200)
        # Check greeting format
        self.assertIn(b"Good evening, Dr. Anita Roy", res.data)
        # Check sidebar
        self.assertIn(b"Case Management", res.data)
        self.assertIn(b"Health Records", res.data)
        # Check patient records table and actions
        self.assertIn(b"Patient Records", res.data)
        self.assertIn(b"View Details", res.data)
        self.assertIn(b"Delete", res.data)
        # Check exact confirmation prompt text and Yes/No options
        self.assertIn(b"Are you sure you want to delete this record?", res.data)
        self.assertIn(b"Yes", res.data)
        self.assertIn(b"No", res.data)
        # Confirm chatbot button is removed
        self.assertNotIn(b"medAiFloatingBtn", res.data)

    def test_06_health_worker_dashboard(self):
        """Test health worker dashboard with Good evening greeting, registry, delete confirmation prompt."""
        with self.client.session_transaction() as sess:
            sess["user_id"] = "usr_nurse_cw"

        res = self.client.get("/nurse/dashboard")
        self.assertEqual(res.status_code, 200)
        # Check greeting format
        self.assertIn(b"Good evening, Pooja Verma", res.data)
        self.assertIn(b"Patient Records Registry", res.data)
        self.assertIn(b"View Details", res.data)
        self.assertIn(b"Delete", res.data)
        # Check exact confirmation prompt text and Yes/No options
        self.assertIn(b"Are you sure you want to delete this record?", res.data)
        self.assertIn(b"Yes", res.data)
        self.assertIn(b"No", res.data)
        # Confirm chatbot button is removed
        self.assertNotIn(b"medAiFloatingBtn", res.data)

    def test_07_health_page(self):
        """Test health page renders all 9 required sections in serial vertical order."""
        with self.client.session_transaction() as sess:
            sess["user_id"] = "usr_patient_cw"

        res = self.client.get("/health")
        self.assertEqual(res.status_code, 200)
        self.assertIn(b"1. Health Summary", res.data)
        self.assertIn(b"Interactive Body Map", res.data)
        self.assertIn(b"WhatsApp Share", res.data)
        self.assertIn(b"2. General Health", res.data)
        self.assertIn(b"3. Health Assessments", res.data)
        self.assertIn(b"4. Screening Tests", res.data)
        self.assertIn(b"5. Pathology Results", res.data)
        self.assertIn(b"6. Vitals Tracker", res.data)
        self.assertIn(b"7. Documents &amp; Images", res.data)
        self.assertIn(b"8. My Prescriptions", res.data)
        self.assertIn(b"9. Medical History", res.data)
        # Confirm chatbot button is removed
        self.assertNotIn(b"medAiFloatingBtn", res.data)

    def test_08_profile_page(self):
        """Test profile page: 4 vertical cards (My Family, Case Referrals, Saved Addresses, Support), Wallet/Invoices removed, and delete account."""
        with self.client.session_transaction() as sess:
            sess["user_id"] = "usr_patient_cw"

        res = self.client.get("/profile")
        self.assertEqual(res.status_code, 200)
        # 4 required cards
        self.assertIn(b"My Family", res.data)
        self.assertIn(b"Case Referrals", res.data)
        self.assertIn(b"Saved Addresses", res.data)
        self.assertIn(b"Support", res.data)
        # Wallet and Invoices must NOT be present
        self.assertNotIn(b"Wallet", res.data)
        self.assertNotIn(b"Invoices", res.data)
        # Session controls
        self.assertIn(b"Log Out", res.data)
        self.assertIn(b"Delete My Account", res.data)
        self.assertIn(b"Permanently Delete Your Account?", res.data)
        # Confirm chatbot button is removed
        self.assertNotIn(b"medAiFloatingBtn", res.data)

    def test_09_case_controls_forward_reject_delete(self):
        """Test case management APIs: forward, reject, and delete."""
        with self.client.session_transaction() as sess:
            sess["user_id"] = "usr_doctor_cw"

        # Reject case
        res_rej = self.client.post("/cases/case_cw_test1/reject", json={"reason": "Incomplete intake"})
        self.assertEqual(res_rej.status_code, 200)
        self.assertTrue(res_rej.get_json()["success"])

        # Forward case
        res_fwd = self.client.post("/cases/case_cw_test1/forward")
        self.assertEqual(res_fwd.status_code, 200)
        self.assertTrue(res_fwd.get_json()["success"])

        # Delete case
        res_del = self.client.post("/cases/case_cw_test1/delete")
        self.assertEqual(res_del.status_code, 200)
        self.assertTrue(res_del.get_json()["success"])

    def test_10_account_deletion(self):
        """Test user account deletion route."""
        # Create a temporary user to delete
        db = SessionLocal()
        try:
            creds = hash_password("Pass1234!")
            now = datetime.now().strftime("%Y-%m-%d %I:%M %p")
            del_user = User(
                id="usr_to_delete_cw",
                name="Delete Me",
                username="del_me_user",
                password_hash=creds["hash"],
                salt=creds["salt"],
                role="Patient",
                status="ACTIVE",
                created_at=now,
                updated_at=now
            )
            db.add(del_user)
            db.commit()
        finally:
            db.close()

        with self.client.session_transaction() as sess:
            sess["user_id"] = "usr_to_delete_cw"

        res = self.client.post("/profile/delete-account")
        self.assertEqual(res.status_code, 200)
        self.assertTrue(res.get_json()["success"])

        # Verify user is gone from DB
        db = SessionLocal()
        try:
            u = db.query(User).filter_by(id="usr_to_delete_cw").first()
            self.assertIsNone(u)
        finally:
            db.close()

if __name__ == "__main__":
    unittest.main()
