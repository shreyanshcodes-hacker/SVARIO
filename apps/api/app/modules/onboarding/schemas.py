"""Pydantic schemas and strict input validators for Stage 2 Business Onboarding."""

import re
from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
from app.modules.organizations.schemas import (
    OrganizationDetailResponse,
    OrganizationIndustry,
)

EMAIL_REGEX = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
PHONE_REGEX = re.compile(r"^\+?[0-9][0-9\-\s()]{5,22}$")
URL_REGEX = re.compile(r"^https?://[^\s/$.?#].[^\s]*$", re.IGNORECASE)
TIME_24H_REGEX = re.compile(r"^(?:[01]\d|2[0-3]):[0-5]\d$")


class LanguageCode(str, Enum):
    """Supported initial languages for Stage 2 onboarding."""

    ENGLISH = "en"
    HINDI = "hi"
    HINGLISH = "hinglish"


class AssistantPersonality(str, Enum):
    """Supported assistant personality presets."""

    PROFESSIONAL = "professional"
    FRIENDLY = "friendly"
    WARM = "warm"


class AssistantResponseStyle(str, Enum):
    """Supported assistant response style presets."""

    CONCISE = "concise"
    BALANCED = "balanced"
    DETAILED = "detailed"


class EscalationMethod(str, Enum):
    """Supported human escalation contact methods."""

    PHONE = "phone"
    EMAIL = "email"
    EITHER = "either"


class OnboardingStepId(str, Enum):
    """Ordered onboarding steps in Stage 2."""

    INDUSTRY = "industry"
    PROFILE = "profile"
    HOURS = "hours"
    LANGUAGES = "languages"
    ASSISTANT = "assistant"
    FAQS = "faqs"
    ESCALATION = "escalation"
    REVIEW = "review"


def _clean_optional_str(value: Optional[str]) -> Optional[str]:
    if value is None:
        return None
    trimmed = value.strip()
    return trimmed if trimmed else None


class UpdateIndustryRequest(BaseModel):
    """Request to confirm or update organization industry (Owner/Admin only)."""

    model_config = ConfigDict(extra="forbid")

    industry: OrganizationIndustry


class BusinessProfileUpdateRequest(BaseModel):
    """Payload for creating or updating the organization's business profile."""

    model_config = ConfigDict(extra="forbid")

    display_name: str = Field(..., min_length=2, max_length=120)
    description: Optional[str] = Field(default=None, max_length=1000)
    phone: Optional[str] = Field(default=None, max_length=32)
    email: Optional[str] = Field(default=None, max_length=160)
    website: Optional[str] = Field(default=None, max_length=255)
    address: Optional[str] = Field(default=None, max_length=255)
    city: Optional[str] = Field(default=None, max_length=100)
    state: Optional[str] = Field(default=None, max_length=100)
    country: Optional[str] = Field(default=None, max_length=100)
    postal_code: Optional[str] = Field(default=None, max_length=32)
    timezone: str = Field(default="UTC", min_length=2, max_length=64)

    @field_validator("display_name")
    @classmethod
    def validate_display_name(cls, value: str) -> str:
        trimmed = value.strip()
        if len(trimmed) < 2:
            raise ValueError("Business name must contain at least 2 characters.")
        return trimmed

    @field_validator(
        "description",
        "address",
        "city",
        "state",
        "country",
        "postal_code",
        mode="before",
    )
    @classmethod
    def clean_optional_fields(cls, value: Optional[str]) -> Optional[str]:
        return _clean_optional_str(value)

    @field_validator("email")
    @classmethod
    def validate_email(cls, value: Optional[str]) -> Optional[str]:
        cleaned = _clean_optional_str(value)
        if cleaned is not None and not EMAIL_REGEX.match(cleaned):
            raise ValueError("Invalid email address format.")
        return cleaned

    @field_validator("phone")
    @classmethod
    def validate_phone(cls, value: Optional[str]) -> Optional[str]:
        cleaned = _clean_optional_str(value)
        if cleaned is not None and not PHONE_REGEX.match(cleaned):
            raise ValueError(
                "Invalid phone number format. Use digits, spaces, hyphens, or leading +."
            )
        return cleaned

    @field_validator("website")
    @classmethod
    def validate_website(cls, value: Optional[str]) -> Optional[str]:
        cleaned = _clean_optional_str(value)
        if cleaned is not None and not URL_REGEX.match(cleaned):
            raise ValueError("Website must be a valid URL starting with http:// or https://.")
        return cleaned

    @field_validator("timezone")
    @classmethod
    def validate_timezone(cls, value: str) -> str:
        trimmed = value.strip()
        if len(trimmed) < 2:
            raise ValueError("Timezone must be at least 2 characters.")
        return trimmed


class BusinessProfileResponse(BaseModel):
    """Persisted business profile representation."""

    id: UUID
    organization_id: UUID
    business_id: UUID
    display_name: str
    description: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    website: Optional[str] = None
    address: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    country: Optional[str] = None
    postal_code: Optional[str] = None
    timezone: str
    created_at: datetime
    updated_at: datetime


class WeekdayHoursItem(BaseModel):
    """Single weekday operating schedule (0 = Sunday .. 6 = Saturday)."""

    model_config = ConfigDict(extra="forbid")

    weekday: int = Field(..., ge=0, le=6, description="0=Sunday .. 6=Saturday")
    is_closed: bool = Field(default=False)
    opens_at: Optional[str] = Field(default="09:00", description="HH:MM in 24-hour time")
    closes_at: Optional[str] = Field(default="18:00", description="HH:MM in 24-hour time")
    is_overnight: bool = Field(
        default=False,
        description="Set true only when closing time is on the following calendar day",
    )

    @model_validator(mode="after")
    def validate_time_range(self) -> "WeekdayHoursItem":
        if self.is_closed:
            self.opens_at = None
            self.closes_at = None
            self.is_overnight = False
            return self

        if not self.opens_at or not self.closes_at:
            raise ValueError(
                f"Weekday {self.weekday}: opens_at and closes_at are required when open."
            )

        opens = self.opens_at.strip()[:5]
        closes = self.closes_at.strip()[:5]

        if not TIME_24H_REGEX.match(opens):
            raise ValueError(f"Weekday {self.weekday}: opens_at must be in HH:MM 24h format.")
        if not TIME_24H_REGEX.match(closes):
            raise ValueError(f"Weekday {self.weekday}: closes_at must be in HH:MM 24h format.")

        if opens == closes:
            raise ValueError(
                f"Weekday {self.weekday}: opens_at and closes_at cannot be identical."
            )

        if not self.is_overnight and opens > closes:
            raise ValueError(
                f"Weekday {self.weekday}: opens_at ({opens}) must be earlier than closes_at ({closes}) unless is_overnight is enabled."
            )

        if self.is_overnight and opens < closes:
            raise ValueError(
                f"Weekday {self.weekday}: overnight schedule requires opens_at ({opens}) to be later in the day than next-day closes_at ({closes})."
            )

        self.opens_at = opens
        self.closes_at = closes
        return self


class BusinessHoursUpdateRequest(BaseModel):
    """Weekly operating schedule update payload."""

    model_config = ConfigDict(extra="forbid")

    timezone: str = Field(default="UTC", min_length=2, max_length=64)
    schedule: List[WeekdayHoursItem] = Field(..., min_length=7, max_length=7)

    @model_validator(mode="after")
    def validate_full_week(self) -> "BusinessHoursUpdateRequest":
        weekdays = [item.weekday for item in self.schedule]
        if sorted(weekdays) != [0, 1, 2, 3, 4, 5, 6]:
            raise ValueError(
                "Weekly schedule must include exactly one entry for each weekday 0 (Sunday) through 6 (Saturday)."
            )
        self.schedule = sorted(self.schedule, key=lambda x: x.weekday)
        return self


class BusinessHoursResponse(BaseModel):
    """Weekly operating schedule response."""

    organization_id: UUID
    business_id: UUID
    timezone: str
    schedule: List[WeekdayHoursItem]


class BusinessLanguageItemResponse(BaseModel):
    """Single persisted business language entry."""

    id: UUID
    organization_id: UUID
    business_id: UUID
    language_code: LanguageCode
    is_primary: bool
    created_at: datetime


class BusinessLanguagesUpdateRequest(BaseModel):
    """Update primary and additional supported languages for the business."""

    model_config = ConfigDict(extra="forbid")

    primary_language: LanguageCode = Field(default=LanguageCode.ENGLISH)
    supported_languages: List[LanguageCode] = Field(
        default_factory=lambda: [LanguageCode.ENGLISH], min_length=1
    )

    @model_validator(mode="after")
    def ensure_primary_in_supported(self) -> "BusinessLanguagesUpdateRequest":
        deduped: List[LanguageCode] = []
        for lang in [self.primary_language, *self.supported_languages]:
            if lang not in deduped:
                deduped.append(lang)
        self.supported_languages = deduped
        return self


class BusinessLanguagesResponse(BaseModel):
    """Configured language settings for a business."""

    organization_id: UUID
    business_id: UUID
    primary_language: LanguageCode
    supported_languages: List[LanguageCode]
    entries: List[BusinessLanguageItemResponse]


class AssistantSettingsUpdateRequest(BaseModel):
    """Update AI voice assistant configuration (Stage 2 configuration only)."""

    model_config = ConfigDict(extra="forbid")

    assistant_name: str = Field(..., min_length=2, max_length=80)
    greeting: str = Field(..., min_length=5, max_length=500)
    personality: AssistantPersonality = Field(default=AssistantPersonality.PROFESSIONAL)
    response_style: AssistantResponseStyle = Field(default=AssistantResponseStyle.BALANCED)
    enabled: bool = Field(default=False)

    @field_validator("assistant_name", "greeting")
    @classmethod
    def strip_text(cls, value: str) -> str:
        trimmed = value.strip()
        if not trimmed:
            raise ValueError("Field cannot be empty or whitespace only.")
        return trimmed


class AssistantSettingsResponse(BaseModel):
    """Persisted AI assistant configuration."""

    id: UUID
    organization_id: UUID
    business_id: UUID
    assistant_name: str
    greeting: str
    personality: AssistantPersonality
    response_style: AssistantResponseStyle
    enabled: bool
    created_at: datetime
    updated_at: datetime


class BusinessFaqCreateRequest(BaseModel):
    """Payload to create a new business FAQ item."""

    model_config = ConfigDict(extra="forbid")

    question: str = Field(..., min_length=3, max_length=500)
    answer: str = Field(..., min_length=2, max_length=2000)
    category: str = Field(default="general", min_length=2, max_length=80)
    is_active: bool = Field(default=True)
    sort_order: int = Field(default=0, ge=0, le=10000)

    @field_validator("question", "answer", "category")
    @classmethod
    def validate_nonempty_text(cls, value: str) -> str:
        trimmed = value.strip()
        if len(trimmed) < 2:
            raise ValueError("Value must contain at least 2 non-whitespace characters.")
        return trimmed


class BusinessFaqUpdateRequest(BaseModel):
    """Payload to update an existing business FAQ item."""

    model_config = ConfigDict(extra="forbid")

    question: Optional[str] = Field(default=None, min_length=3, max_length=500)
    answer: Optional[str] = Field(default=None, min_length=2, max_length=2000)
    category: Optional[str] = Field(default=None, min_length=2, max_length=80)
    is_active: Optional[bool] = None
    sort_order: Optional[int] = Field(default=None, ge=0, le=10000)


class BusinessFaqResponse(BaseModel):
    """Persisted business FAQ item."""

    id: UUID
    organization_id: UUID
    business_id: UUID
    question: str
    answer: str
    category: str
    is_active: bool
    sort_order: int
    created_at: datetime
    updated_at: datetime


class FaqTemplateExample(BaseModel):
    """Editable starter FAQ example (non-factual placeholder template)."""

    industry: OrganizationIndustry
    question: str
    answer_placeholder: str
    category: str


INDUSTRY_FAQ_TEMPLATES: Dict[OrganizationIndustry, List[FaqTemplateExample]] = {
    OrganizationIndustry.SALON: [
        FaqTemplateExample(
            industry=OrganizationIndustry.SALON,
            question="What are your opening hours?",
            answer_placeholder="[Edit with your salon's actual opening days and hours]",
            category="hours",
        ),
        FaqTemplateExample(
            industry=OrganizationIndustry.SALON,
            question="Where are you located?",
            answer_placeholder="[Edit with your salon's street address, landmark, and parking info]",
            category="location",
        ),
        FaqTemplateExample(
            industry=OrganizationIndustry.SALON,
            question="How can I book an appointment?",
            answer_placeholder="[Edit with your salon's booking policy and front-desk instructions]",
            category="booking",
        ),
    ],
    OrganizationIndustry.CLINIC: [
        FaqTemplateExample(
            industry=OrganizationIndustry.CLINIC,
            question="What are your consultation hours?",
            answer_placeholder="[Edit with your clinic's outpatient consultation timings]",
            category="hours",
        ),
        FaqTemplateExample(
            industry=OrganizationIndustry.CLINIC,
            question="Which specialities are available?",
            answer_placeholder="[Edit with the clinical specialities offered at your practice]",
            category="services",
        ),
        FaqTemplateExample(
            industry=OrganizationIndustry.CLINIC,
            question="How do I contact reception?",
            answer_placeholder="[Edit with your clinic's reception phone number and email]",
            category="contact",
        ),
    ],
    OrganizationIndustry.HOSPITAL: [
        FaqTemplateExample(
            industry=OrganizationIndustry.HOSPITAL,
            question="What are your visiting hours?",
            answer_placeholder="[Edit with your hospital's general ward and ICU visiting hours]",
            category="visiting",
        ),
        FaqTemplateExample(
            industry=OrganizationIndustry.HOSPITAL,
            question="Where is the OPD?",
            answer_placeholder="[Edit with your hospital's OPD building/floor directions]",
            category="navigation",
        ),
        FaqTemplateExample(
            industry=OrganizationIndustry.HOSPITAL,
            question="How can I contact the department?",
            answer_placeholder="[Edit with your hospital switchboard or department extension details]",
            category="contact",
        ),
    ],
}


class EscalationSettingsUpdateRequest(BaseModel):
    """Payload to update human escalation settings."""

    model_config = ConfigDict(extra="forbid")

    enabled: bool = Field(default=True)
    contact_name: Optional[str] = Field(default=None, max_length=120)
    contact_email: Optional[str] = Field(default=None, max_length=160)
    contact_phone: Optional[str] = Field(default=None, max_length=32)
    preferred_method: EscalationMethod = Field(default=EscalationMethod.PHONE)
    escalation_instructions: Optional[str] = Field(default=None, max_length=1000)

    @field_validator("contact_name", "escalation_instructions", mode="before")
    @classmethod
    def clean_strings(cls, value: Optional[str]) -> Optional[str]:
        return _clean_optional_str(value)

    @field_validator("contact_email")
    @classmethod
    def validate_contact_email(cls, value: Optional[str]) -> Optional[str]:
        cleaned = _clean_optional_str(value)
        if cleaned is not None and not EMAIL_REGEX.match(cleaned):
            raise ValueError("Invalid escalation contact email address.")
        return cleaned

    @field_validator("contact_phone")
    @classmethod
    def validate_contact_phone(cls, value: Optional[str]) -> Optional[str]:
        cleaned = _clean_optional_str(value)
        if cleaned is not None and not PHONE_REGEX.match(cleaned):
            raise ValueError("Invalid escalation contact phone number.")
        return cleaned

    @model_validator(mode="after")
    def validate_enabled_contact_requirements(self) -> "EscalationSettingsUpdateRequest":
        if not self.enabled:
            return self

        if not self.contact_name or len(self.contact_name) < 2:
            raise ValueError(
                "Escalation contact_name (at least 2 characters) is required when escalation is enabled."
            )

        if self.preferred_method == EscalationMethod.PHONE and not self.contact_phone:
            raise ValueError(
                "contact_phone is required when preferred_method is 'phone'."
            )
        if self.preferred_method == EscalationMethod.EMAIL and not self.contact_email:
            raise ValueError(
                "contact_email is required when preferred_method is 'email'."
            )
        if (
            self.preferred_method == EscalationMethod.EITHER
            and not self.contact_phone
            and not self.contact_email
        ):
            raise ValueError(
                "At least one of contact_phone or contact_email is required when escalation is enabled."
            )
        return self


class EscalationSettingsResponse(BaseModel):
    """Persisted human escalation configuration."""

    id: UUID
    organization_id: UUID
    business_id: UUID
    enabled: bool
    contact_name: Optional[str] = None
    contact_email: Optional[str] = None
    contact_phone: Optional[str] = None
    preferred_method: EscalationMethod
    escalation_instructions: Optional[str] = None
    created_at: datetime
    updated_at: datetime


class HealthcareSafeguardNotice(BaseModel):
    """Mandatory administrative & healthcare safeguard boundaries."""

    applies_to_healthcare: bool
    administrative_only: bool = True
    prohibited_actions: List[str] = Field(
        default_factory=lambda: [
            "No medical diagnosis",
            "No prescriptions or medication advice",
            "No treatment recommendations",
            "No clinical decision-making",
            "Do not collect unnecessary patient medical information",
        ]
    )
    emergency_directive: str = (
        "Emergency-related requests must be directed immediately to local emergency "
        "services or the hospital/clinic emergency channel."
    )


class OnboardingProgressUpdateRequest(BaseModel):
    """Update onboarding progress step and completion status."""

    model_config = ConfigDict(extra="forbid")

    current_step: OnboardingStepId
    completed_steps: List[OnboardingStepId] = Field(default_factory=list)
    is_completed: bool = Field(default=False)

    @model_validator(mode="after")
    def deduplicate_steps(self) -> "OnboardingProgressUpdateRequest":
        unique_steps: List[OnboardingStepId] = []
        for step in self.completed_steps:
            if step not in unique_steps:
                unique_steps.append(step)
        self.completed_steps = unique_steps
        return self


class OnboardingProgressResponse(BaseModel):
    """Persisted onboarding progress tracker."""

    id: UUID
    organization_id: UUID
    business_id: UUID
    current_step: OnboardingStepId
    completed_steps: List[OnboardingStepId]
    is_completed: bool
    completed_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime


class OnboardingBundleResponse(BaseModel):
    """Complete organization-scoped Stage 2 onboarding state bundle."""

    organization: OrganizationDetailResponse
    business_id: UUID
    profile: BusinessProfileResponse
    hours: BusinessHoursResponse
    languages: BusinessLanguagesResponse
    assistant: AssistantSettingsResponse
    faqs: List[BusinessFaqResponse]
    faq_templates: List[FaqTemplateExample]
    escalation: EscalationSettingsResponse
    healthcare_safeguards: HealthcareSafeguardNotice
    progress: OnboardingProgressResponse
