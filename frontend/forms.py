"""Frontend Form Validation and Processing Schemas.

Provides validation structures for patient demographics, multimodal symptoms,
physiological vitals, specialist referrals, and contact submissions.
"""

from typing import Dict, Any, List, Tuple

class PatientCaseForm:
    """Validates patient registration and intake data."""

    @staticmethod
    def validate(data: Dict[str, Any]) -> Tuple[bool, List[str]]:
        errors = []
        if not data.get("patientId"):
            errors.append("Patient ID is required.")
        if not data.get("age"):
            errors.append("Patient age is required.")
        else:
            try:
                age_val = int(data["age"])
                if age_val < 0 or age_val > 130:
                    errors.append("Please enter a valid age between 0 and 130.")
            except ValueError:
                errors.append("Age must be an integer.")

        if not data.get("gender"):
            errors.append("Gender selection is required.")
        if not data.get("language"):
            errors.append("Preferred language is required.")
        if not data.get("consentObtained"):
            errors.append("Patient or guardian consent confirmation is mandatory.")

        return len(errors) == 0, errors

class VitalsForm:
    """Validates physical physiological measurements."""

    @staticmethod
    def validate(vitals: Dict[str, Any]) -> Tuple[bool, List[str]]:
        errors = []
        # SpO2
        if vitals.get("spo2"):
            try:
                spo2_num = float(vitals["spo2"])
                if spo2_num < 40 or spo2_num > 100:
                    errors.append("SpO2 must be between 40% and 100%.")
            except ValueError:
                errors.append("SpO2 must be a valid number.")

        # Temperature
        if vitals.get("temperature"):
            try:
                temp_num = float(vitals["temperature"])
                if temp_num < 30 or temp_num > 45:
                    errors.append("Body temperature in Celsius must be between 30°C and 45°C.")
            except ValueError:
                errors.append("Temperature must be a valid number.")

        # Blood Pressure
        if vitals.get("bloodPressureSys"):
            try:
                sys_num = int(vitals["bloodPressureSys"])
                if sys_num < 50 or sys_num > 300:
                    errors.append("Systolic BP must be between 50 and 300 mmHg.")
            except ValueError:
                errors.append("Systolic BP must be an integer.")

        if vitals.get("bloodPressureDia"):
            try:
                dia_num = int(vitals["bloodPressureDia"])
                if dia_num < 30 or dia_num > 200:
                    errors.append("Diastolic BP must be between 30 and 200 mmHg.")
            except ValueError:
                errors.append("Diastolic BP must be an integer.")

        return len(errors) == 0, errors

class ReferralForm:
    """Validates specialist referral dispatch data."""

    @staticmethod
    def validate(data: Dict[str, Any]) -> Tuple[bool, List[str]]:
        errors = []
        if not data.get("destinationFacility"):
            errors.append("Destination Facility is required.")
        if not data.get("destinationDepartment"):
            errors.append("Destination Department is required.")
        if not data.get("reason"):
            errors.append("Clinical reason for referral is mandatory.")
        return len(errors) == 0, errors

class ContactForm:
    """Validates contact and facility support inquiries."""

    @staticmethod
    def validate(data: Dict[str, Any]) -> Tuple[bool, List[str]]:
        errors = []
        if not data.get("name"):
            errors.append("Name is required.")
        if not data.get("email"):
            errors.append("Email address is required.")
        elif "@" not in data["email"]:
            errors.append("Please enter a valid email address.")
        if not data.get("message"):
            errors.append("Message content is required.")
        return len(errors) == 0, errors
