"""Phase 4C & 4J — Typed Intent Classification, Safety Flagging & Language Detection.

Supports:
- All 14 canonical Stage 4 intents (`greeting`, `business_information`, `opening_hours`,
  `location`, `services_enquiry`, `pricing_enquiry`, `speciality_enquiry`,
  `department_enquiry`, `booking_intent`, `rescheduling_intent`, `cancellation_intent`,
  `human_support`, `emergency_intent`, `unknown`).
- Multilingual detection across English (`en`), Hindi (`hi`), and Hinglish (`hinglish`).
- Mandatory healthcare & prompt-injection safety flag detection.
- Pydantic-validated `IntentClassificationResult` outputs.
"""

import re
from typing import Any, Dict, List, Optional, Tuple
from app.agents.schemas import (
    AgentIntent,
    AgentToolName,
    IntentClassificationResult,
    SafetyFlag,
)
from app.modules.onboarding.schemas import LanguageCode
from app.modules.organizations.schemas import OrganizationIndustry

DEVANAGARI_REGEX = re.compile(r"[\u0900-\u097F]")

HINGLISH_MARKERS = {
    "kya",
    "kab",
    "kahan",
    "kaha",
    "kitna",
    "kitne",
    "kaise",
    "hai",
    "hain",
    "ho",
    "khula",
    "band",
    "baje",
    "mujhe",
    "meri",
    "mera",
    "chahiye",
    "karna",
    "karni",
    "karwana",
    "baat",
    "batao",
    "bataiye",
    "namaste",
    "dhanyawad",
    "shukriya",
    "dawai",
    "ilaaj",
    "doctor",
    "dukaan",
}

EMERGENCY_PATTERNS = [
    r"\b(chest pain|heart attack|stroke|can'?t breathe|cannot breathe|breathing difficulty|shortness of breath|severe bleeding|heavy bleeding|unconscious|fainted|seizure|overdose|suicid|life threatening|ambulance)\b",
    r"\b(medical emergency|urgent emergency|emergency room|casualty ward)\b",
    r"(सीने में दर्द|साँस नहीं|सांस लेने में तकलीफ|खून बह रहा|बेहोश|हार्ट अटैक|आपातकाल|इमरजेंसी)",
    r"\b(saans nahi|seene mein dard|khoon bah|behosh|jaan ka khatra)\b",
]

DIAGNOSIS_PATTERNS = [
    r"\b(diagnose|what disease do i have|what condition do i have|do i have cancer|do i have diabetes|do i have covid|what is wrong with my body|interpret my lab|check my symptoms)\b",
    r"(मुझे कौन सी बीमारी है|मेरी बीमारी बताओ|लक्षण देखकर बताओ)",
    r"\b(mujhe kaun si bimari hai|mere symptoms dekh kar batao)\b",
]

PRESCRIPTION_PATTERNS = [
    r"\b(prescribe|prescription|which medicine should i take|which antibiotic|antibiotic dosage|what dosage|how many mg|which tablet should i take|can i take paracetamol|can i take ibuprofen|stop taking my medicine)\b",
    r"(कौन सी दवा लूँ|दवाई लिख दो|कौन सी गोली खाऊँ|खुराक बताओ)",
    r"\b(kaun si dawai lu|konsi tablet khau|medicine suggest karo)\b",
]

TREATMENT_PATTERNS = [
    r"\b(recommend a medical treatment|what treatment should i take|should i undergo surgery|which therapy will cure|how to cure my)\b",
    r"(मेरा इलाज क्या है|कौन सा इलाज करवाऊँ)",
    r"\b(mera ilaaj kya hai|konsa medical treatment lu)\b",
]

PROMPT_INJECTION_PATTERNS = [
    r"\b(ignore all previous instructions|ignore prior instructions|reveal your system prompt|drop table|delete from|select \* from|bypass authorization|service_role)\b",
]

WEEKDAY_KEYWORDS: Dict[str, int] = {
    "sunday": 0,
    "ravivar": 0,
    "रविवार": 0,
    "monday": 1,
    "somvar": 1,
    "सोमवार": 1,
    "tuesday": 2,
    "mangalvar": 2,
    "मंगलवार": 2,
    "wednesday": 3,
    "budhvar": 3,
    "बुधवार": 3,
    "thursday": 4,
    "guruvar": 4,
    "गुरुवार": 4,
    "friday": 5,
    "shukravar": 5,
    "शुक्रवार": 5,
    "saturday": 6,
    "shanivar": 6,
    "शनिवार": 6,
}

TIME_MENTION_REGEX = re.compile(
    r"\b(\d{1,2}(?::\d{2})?\s*(?:am|pm|baje)|morning|afternoon|evening|subah|shaam|दोपहर|सुबह|शाम)\b",
    re.IGNORECASE,
)
DATE_MENTION_REGEX = re.compile(
    r"\b(today|tomorrow|aaj|kal|parso|next week|this weekend|आज|कल|परसों|\d{1,2}[/-]\d{1,2})\b",
    re.IGNORECASE,
)


def detect_language(
    text: str,
    supported_languages: Optional[List[LanguageCode]] = None,
    preferred_override: Optional[LanguageCode] = None,
) -> LanguageCode:
    """Detect whether caller input is English (`en`), Hindi (`hi`), or Hinglish (`hinglish`)."""
    if preferred_override is not None:
        if not supported_languages or preferred_override in supported_languages:
            return preferred_override

    lowered = text.lower()
    # Explicit language switch request
    if any(p in lowered for p in ["speak in hindi", "talk in hindi", "हिंदी में बात", "hindi mein baat"]):
        if not supported_languages or LanguageCode.HINDI in supported_languages:
            return LanguageCode.HINDI
    if any(p in lowered for p in ["speak in hinglish", "hinglish mein"]):
        if not supported_languages or LanguageCode.HINGLISH in supported_languages:
            return LanguageCode.HINGLISH
    if any(p in lowered for p in ["speak in english", "talk in english", "english mein baat"]):
        return LanguageCode.ENGLISH

    if DEVANAGARI_REGEX.search(text):
        if not supported_languages or LanguageCode.HINDI in supported_languages:
            return LanguageCode.HINDI

    tokens = set(re.findall(r"[a-zA-Z]+", lowered))
    hinglish_hits = tokens.intersection(HINGLISH_MARKERS)
    if len(hinglish_hits) >= 2 or (
        len(hinglish_hits) == 1
        and any(w in hinglish_hits for w in {"kya", "kab", "kahan", "kitna", "namaste", "batao", "bataiye", "chahiye"})
    ):
        if not supported_languages or LanguageCode.HINGLISH in supported_languages:
            return LanguageCode.HINGLISH
        if supported_languages and LanguageCode.HINDI in supported_languages:
            return LanguageCode.HINDI

    return LanguageCode.ENGLISH


def _detect_safety_flags(
    text: str, industry: OrganizationIndustry
) -> List[SafetyFlag]:
    """Inspect caller utterance for emergency, clinical, or injection flags."""
    flags: List[SafetyFlag] = []
    lowered = text.lower()

    for pattern in PROMPT_INJECTION_PATTERNS:
        if re.search(pattern, lowered, re.IGNORECASE):
            flags.append(SafetyFlag.PROMPT_INJECTION_OR_POLICY_BYPASS)
            break

    for pattern in EMERGENCY_PATTERNS:
        if re.search(pattern, lowered, re.IGNORECASE):
            flags.append(SafetyFlag.MEDICAL_EMERGENCY_DETECTED)
            break

    is_healthcare = industry in {
        OrganizationIndustry.CLINIC,
        OrganizationIndustry.HOSPITAL,
    }
    if is_healthcare:
        for pattern in DIAGNOSIS_PATTERNS:
            if re.search(pattern, lowered, re.IGNORECASE):
                flags.append(SafetyFlag.CLINICAL_DIAGNOSIS_REQUEST)
                break
        for pattern in PRESCRIPTION_PATTERNS:
            if re.search(pattern, lowered, re.IGNORECASE):
                flags.append(SafetyFlag.PRESCRIPTION_OR_MEDICATION_REQUEST)
                break
        for pattern in TREATMENT_PATTERNS:
            if re.search(pattern, lowered, re.IGNORECASE):
                flags.append(SafetyFlag.TREATMENT_RECOMMENDATION_REQUEST)
                break

    return flags


def _extract_entities(text: str) -> Dict[str, Any]:
    """Extract structured entities (weekday, date, time, topic keywords) from caller input."""
    entities: Dict[str, Any] = {}
    lowered = text.lower()

    for word, day_idx in WEEKDAY_KEYWORDS.items():
        if word in lowered:
            entities["weekday"] = day_idx
            entities["weekday_name"] = word
            break

    time_match = TIME_MENTION_REGEX.search(text)
    if time_match:
        entities["preferred_time"] = time_match.group(0).strip()

    date_match = DATE_MENTION_REGEX.search(text)
    if date_match:
        entities["preferred_date"] = date_match.group(0).strip()

    for service_kw in [
        "haircut",
        "hair spa",
        "keratin",
        "facial",
        "manicure",
        "pedicure",
        "bridal",
        "coloring",
        "consultation",
        "dental",
        "dermatology",
        "cardiology",
        "orthopedics",
        "pediatrics",
        "neurology",
        "opd",
        "xray",
        "mri",
    ]:
        if service_kw in lowered:
            entities["topic"] = service_kw
            break

    return entities


class IntentClassifier:
    """Deterministic, schema-validated Stage 4 intent classifier."""

    def classify(
        self,
        user_input: str,
        industry: OrganizationIndustry,
        supported_languages: Optional[List[LanguageCode]] = None,
        preferred_language: Optional[LanguageCode] = None,
    ) -> IntentClassificationResult:
        """Classify caller input into a validated `IntentClassificationResult`."""
        cleaned = user_input.strip()
        lowered = cleaned.lower()

        detected_lang = detect_language(
            cleaned,
            supported_languages=supported_languages,
            preferred_override=preferred_language,
        )
        safety_flags = _detect_safety_flags(cleaned, industry=industry)
        entities = _extract_entities(cleaned)
        entities["language"] = detected_lang.value

        # 1. Immediate Emergency Short-Circuit
        if SafetyFlag.MEDICAL_EMERGENCY_DETECTED in safety_flags:
            return IntentClassificationResult(
                intent=AgentIntent.EMERGENCY_INTENT,
                confidence=0.99,
                detected_language=detected_lang,
                extracted_entities=entities,
                missing_information=[],
                requires_tool=False,
                recommended_tool=None,
                requires_human=True,
                safety_flags=safety_flags,
            )

        # 2. Clinical Safety Boundary Short-Circuit (Diagnosis / Prescription / Treatment)
        clinical_flags = {
            SafetyFlag.CLINICAL_DIAGNOSIS_REQUEST,
            SafetyFlag.PRESCRIPTION_OR_MEDICATION_REQUEST,
            SafetyFlag.TREATMENT_RECOMMENDATION_REQUEST,
        }
        if clinical_flags.intersection(safety_flags):
            return IntentClassificationResult(
                intent=AgentIntent.HUMAN_SUPPORT,
                confidence=0.95,
                detected_language=detected_lang,
                extracted_entities=entities,
                missing_information=[],
                requires_tool=True,
                recommended_tool=AgentToolName.REQUEST_HUMAN_ESCALATION,
                requires_human=True,
                safety_flags=safety_flags,
            )

        # 3. Prompt Injection / Policy Bypass
        if SafetyFlag.PROMPT_INJECTION_OR_POLICY_BYPASS in safety_flags:
            return IntentClassificationResult(
                intent=AgentIntent.UNKNOWN,
                confidence=0.95,
                detected_language=detected_lang,
                extracted_entities=entities,
                missing_information=[],
                requires_tool=False,
                recommended_tool=None,
                requires_human=False,
                safety_flags=safety_flags,
            )

        # 4. Human Support / Escalation Intent
        if re.search(
            r"\b(human|person|real agent|staff|manager|receptionist|operator|talk to someone|speak to someone|callback|call me back|insaan se baat|kisi se baat)\b|(इंसान से बात|मैनेजर से बात|स्टाफ से बात)",
            lowered,
        ):
            return IntentClassificationResult(
                intent=AgentIntent.HUMAN_SUPPORT,
                confidence=0.93,
                detected_language=detected_lang,
                extracted_entities=entities,
                missing_information=[],
                requires_tool=True,
                recommended_tool=AgentToolName.REQUEST_HUMAN_ESCALATION,
                requires_human=True,
                safety_flags=safety_flags,
            )

        # 5. Cancellation / Rescheduling / Booking Intents (Stage 4: recognized but never executed)
        if re.search(
            r"\b(cancel my appointment|cancel my booking|cancel booking|cancellation|cancel karna|रद्द करना|कैंसिल)\b",
            lowered,
        ):
            return IntentClassificationResult(
                intent=AgentIntent.CANCELLATION_INTENT,
                confidence=0.91,
                detected_language=detected_lang,
                extracted_entities=entities,
                missing_information=[],
                requires_tool=True,
                recommended_tool=AgentToolName.REQUEST_HUMAN_ESCALATION,
                requires_human=True,
                safety_flags=safety_flags,
            )

        if re.search(
            r"\b(reschedule|change my appointment|postpone|shift my booking|time badalna|समय बदलना)\b",
            lowered,
        ):
            return IntentClassificationResult(
                intent=AgentIntent.RESCHEDULING_INTENT,
                confidence=0.91,
                detected_language=detected_lang,
                extracted_entities=entities,
                missing_information=[],
                requires_tool=True,
                recommended_tool=AgentToolName.REQUEST_HUMAN_ESCALATION,
                requires_human=True,
                safety_flags=safety_flags,
            )

        if re.search(
            r"\b(book an appointment|book a slot|schedule an appointment|make a reservation|appointment book|book karna|appointment chahiye|booking karni|अपॉइंटमेंट बुक|बुकिंग करनी)\b",
            lowered,
        ):
            missing: List[str] = []
            if "topic" not in entities:
                missing.append("preferred_service_or_department")
            if "preferred_date" not in entities and "weekday" not in entities:
                missing.append("preferred_day_or_date")
            if "preferred_time" not in entities:
                missing.append("preferred_time")

            return IntentClassificationResult(
                intent=AgentIntent.BOOKING_INTENT,
                confidence=0.90,
                detected_language=detected_lang,
                extracted_entities=entities,
                missing_information=missing,
                requires_tool=True,
                recommended_tool=AgentToolName.SAVE_CONVERSATION_SUMMARY,
                requires_human=False,
                safety_flags=safety_flags,
            )

        # 6. Department Enquiry (Hospital / Departmental focus)
        if re.search(
            r"\b(department|opd department|ward|icu|radiology|pathology|pharmacy|billing desk|extension number|विभाग|डिपार्टमेंट)\b",
            lowered,
        ):
            return IntentClassificationResult(
                intent=AgentIntent.DEPARTMENT_ENQUIRY,
                confidence=0.89,
                detected_language=detected_lang,
                extracted_entities=entities,
                missing_information=[],
                requires_tool=True,
                recommended_tool=AgentToolName.SEARCH_BUSINESS_KNOWLEDGE,
                requires_human=False,
                safety_flags=safety_flags,
            )

        # 7. Opening Hours / Visiting Hours / OPD Timings
        if re.search(
            r"\b(opening hours|operating hours|business hours|what time do you open|when do you close|visiting hours|consultation hours|opd timings|timings|open on sunday|kitne baje khulta|kab khula)\b|(कब खुलता है|समय क्या है|ओपीडी का समय|मिलने का समय)",
            lowered,
        ):
            return IntentClassificationResult(
                intent=AgentIntent.OPENING_HOURS,
                confidence=0.92,
                detected_language=detected_lang,
                extracted_entities=entities,
                missing_information=[],
                requires_tool=True,
                recommended_tool=AgentToolName.GET_BUSINESS_HOURS,
                requires_human=False,
                safety_flags=safety_flags,
            )

        # 8. Location / Address / Directions / Parking
        if re.search(
            r"\b(where are you located|address|location|directions|landmark|parking|which floor|where is the opd|kahan par hai|pata kya hai)\b|(कहाँ स्थित है|पता कहाँ है|पता क्या है|ओपीडी कहाँ है)",
            lowered,
        ):
            return IntentClassificationResult(
                intent=AgentIntent.LOCATION,
                confidence=0.91,
                detected_language=detected_lang,
                extracted_entities=entities,
                missing_information=[],
                requires_tool=True,
                recommended_tool=AgentToolName.GET_BUSINESS_PROFILE,
                requires_human=False,
                safety_flags=safety_flags,
            )

        # 9. Pricing / Cost / Consultation Fee Enquiry
        if re.search(
            r"\b(price|pricing|cost|how much|charges|rate list|consultation fee|fees|kitna paisa|kitne ka hai)\b|(कीमत क्या है|फीस कितनी है|कितना चार्ज)",
            lowered,
        ):
            missing_price: List[str] = []
            if "topic" not in entities and len(cleaned.split()) <= 4:
                missing_price.append("specific_service_or_consultation")
            return IntentClassificationResult(
                intent=AgentIntent.PRICING_ENQUIRY,
                confidence=0.88,
                detected_language=detected_lang,
                extracted_entities=entities,
                missing_information=missing_price,
                requires_tool=True,
                recommended_tool=AgentToolName.SEARCH_BUSINESS_KNOWLEDGE,
                requires_human=False,
                safety_flags=safety_flags,
            )

        # 10. Speciality Enquiry (Clinic / Hospital focus)
        if re.search(
            r"\b(speciality|specialty|specialities|specialist|dermatologist|dentist|cardiologist|pediatrician|orthopedic|gynecologist|physiotherapy|डॉक्टर|स्पेशलिस्ट|विशेषज्ञ)\b",
            lowered,
        ):
            return IntentClassificationResult(
                intent=AgentIntent.SPECIALITY_ENQUIRY,
                confidence=0.89,
                detected_language=detected_lang,
                extracted_entities=entities,
                missing_information=[],
                requires_tool=True,
                recommended_tool=AgentToolName.SEARCH_BUSINESS_KNOWLEDGE,
                requires_human=False,
                safety_flags=safety_flags,
            )

        # 11. Services Enquiry (Salon / General focus)
        if re.search(
            r"\b(services|haircut|hair spa|keratin|facial|manicure|pedicure|bridal|coloring|menu|treatments offered|kya kya services)\b|(क्या सेवाएं|हेयरकट|फेशियल)",
            lowered,
        ):
            return IntentClassificationResult(
                intent=AgentIntent.SERVICES_ENQUIRY,
                confidence=0.89,
                detected_language=detected_lang,
                extracted_entities=entities,
                missing_information=[],
                requires_tool=True,
                recommended_tool=AgentToolName.SEARCH_BUSINESS_KNOWLEDGE,
                requires_human=False,
                safety_flags=safety_flags,
            )

        # 12. Business Information / Contact Details
        if re.search(
            r"\b(contact number|phone number|email|website|about your business|tell me about|who are you|what is the name of|reception number)\b|(फोन नंबर|ईमेल|जानकारी)",
            lowered,
        ):
            return IntentClassificationResult(
                intent=AgentIntent.BUSINESS_INFORMATION,
                confidence=0.88,
                detected_language=detected_lang,
                extracted_entities=entities,
                missing_information=[],
                requires_tool=True,
                recommended_tool=AgentToolName.GET_BUSINESS_PROFILE,
                requires_human=False,
                safety_flags=safety_flags,
            )

        # 13. Greeting
        if re.search(
            r"^\s*(hello|hi|hey|good morning|good afternoon|good evening|namaste|namaskar|सत श्री अकाल|नमस्ते|हेलो)\b",
            lowered,
        ) and len(cleaned.split()) <= 6:
            return IntentClassificationResult(
                intent=AgentIntent.GREETING,
                confidence=0.96,
                detected_language=detected_lang,
                extracted_entities=entities,
                missing_information=[],
                requires_tool=False,
                recommended_tool=None,
                requires_human=False,
                safety_flags=safety_flags,
            )

        # 14. Unknown / General Question -> try knowledge search first with moderate confidence
        if "?" in cleaned or len(cleaned.split()) >= 4:
            return IntentClassificationResult(
                intent=AgentIntent.UNKNOWN,
                confidence=0.45,
                detected_language=detected_lang,
                extracted_entities=entities,
                missing_information=["clarify_request_topic"],
                requires_tool=True,
                recommended_tool=AgentToolName.SEARCH_BUSINESS_KNOWLEDGE,
                requires_human=False,
                safety_flags=safety_flags,
            )

        return IntentClassificationResult(
            intent=AgentIntent.UNKNOWN,
            confidence=0.30,
            detected_language=detected_lang,
            extracted_entities=entities,
            missing_information=["clarify_request_topic"],
            requires_tool=False,
            recommended_tool=None,
            requires_human=False,
            safety_flags=safety_flags,
        )
