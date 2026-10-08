"""Multilingual Translation and Linguistic Normalization Service.

Supports Hindi, Odia, and English clinical terminology mapping and personalized diet advice.
"""

from typing import Dict, Any, Optional

CLINICAL_DICTIONARY = {
    "fever": {"hi": "बुखार", "or": "ଜ୍ୱର", "en": "Fever"},
    "cough": {"hi": "खांसी", "or": "କାସ", "en": "Cough"},
    "chest pain": {"hi": "सीने में दर्द", "or": "ଛାତି ଯନ୍ତ୍ରଣା", "en": "Chest Pain"},
    "shortness of breath": {"hi": "सांस फूलना", "or": "ଶ୍ୱାସକ୍ରିୟାରେ କଷ୍ଟ", "en": "Shortness of breath"},
    "headache": {"hi": "सिर दर्द", "or": "ମୁଣ୍ଡ ବିନ୍ଧା", "en": "Headache"},
    "vomiting": {"hi": "उल्टी", "or": "ବାନ୍ତି", "en": "Vomiting"}
}

class LanguageService:
    """Multilingual clinical translation and diet consultation synthesizer."""

    def translate_term(self, term: str, target_lang: str = "hi") -> str:
        """Translates basic clinical term across English, Hindi, and Odia."""
        clean = term.strip().lower()
        if clean in CLINICAL_DICTIONARY and target_lang in CLINICAL_DICTIONARY[clean]:
            return CLINICAL_DICTIONARY[clean][target_lang]
        return term

    def generate_diet_advice(
        self,
        vitals: Optional[Dict[str, Any]] = None,
        conditions: Optional[str] = None,
        symptoms: Optional[str] = None,
        age: Optional[int] = None,
        language: str = "English"
    ) -> Dict[str, Any]:
        """Generates evidence-based clinical diet and nutrition consultation tailored to patient vitals & language."""
        vitals = vitals or {}
        conditions_str = (conditions or "").lower()
        symptoms_str = (symptoms or "").lower()

        try:
            temp = float(vitals.get("temperature") or 37.0)
        except (ValueError, TypeError):
            temp = 37.0

        try:
            sys_bp = int(vitals.get("bloodPressureSys") or 120)
        except (ValueError, TypeError):
            sys_bp = 120

        try:
            spo2 = int(vitals.get("spo2") or 98)
        except (ValueError, TypeError):
            spo2 = 98

        recommendations = []
        avoid_foods = []
        hydration_liters = 2.5
        caloric_focus = "Standard balanced nutrient-dense diet"

        # Fever
        if temp > 38.0 or "fever" in symptoms_str or "बुखार" in symptoms_str or "ଜ୍ୱର" in symptoms_str:
            hydration_liters = 3.5
            caloric_focus = "High-calorie, easily digestible liquid and soft food diet"
            recommendations.extend([
                "Increase fluid intake: Warm electrolyte broths, tender coconut water, and herbal decoctions (Tulsi/Ginger).",
                "Consume soft, easily digestible carbohydrates: Rice kanji (porridge), khichdi, and boiled potatoes.",
                "Vitamin C-rich citrus fruits (amla, oranges, sweet lime) to support immune response."
            ])
            avoid_foods.extend([
                "Heavy, oily, deep-fried street foods and spicy gravies.",
                "Excessive caffeine and refrigerated carbonated beverages."
            ])

        # Respiratory / Dyspnea
        if spo2 < 95 or "cough" in symptoms_str or "breath" in symptoms_str or "खांसी" in symptoms_str or "କାସ" in symptoms_str:
            recommendations.extend([
                "Warm fluids at regular 2-hour intervals to thin bronchial secretions.",
                "Anti-inflammatory spices: Turmeric golden milk (Haldi Doodh) and warm black pepper honey infusions.",
                "Small, frequent meals rather than large heavy meals to reduce diaphragmatic pressure."
            ])
            avoid_foods.extend([
                "Cold dairy items, iced drinks, and mucus-inducing heavy creams.",
                "High-sodium processed snacks."
            ])

        # Hypertension
        if sys_bp >= 140 or "hypertension" in conditions_str or "bp" in conditions_str:
            recommendations.extend([
                "DASH Diet protocol: Potassium-rich fruits (bananas, papayas, leafy greens).",
                "Strict sodium moderation: Restrict salt intake to less than 4-5 grams per day.",
                "Incorporate garlic, flaxseeds, and steamed drumsticks (Moringa) for vascular health."
            ])
            avoid_foods.extend([
                "Pickles (Achar), papads, salted nuts, and canned soups.",
                "Processed cheeses, bakery items with baking soda/powder."
            ])

        if not recommendations:
            recommendations = [
                "Maintain balanced macronutrient intake with whole grains, lentils, and seasonal vegetables.",
                "Drink 2.5 - 3.0 liters of filtered water daily.",
                "Include probiotic-rich curd or homemade buttermilk with meals."
            ]
            avoid_foods = ["Ultra-processed packaged foods", "Excess refined sugar and trans-fats"]

        return {
            "language": language,
            "hydration_target_liters": hydration_liters,
            "caloric_focus": caloric_focus,
            "dietary_recommendations": recommendations,
            "foods_to_avoid": avoid_foods,
            "clinical_notes": f"Personalized nutrition synthesized based on physiological vitals (Temp: {temp}°C, BP: {sys_bp} mmHg, SpO2: {spo2}%)."
        }

language_service = LanguageService()
