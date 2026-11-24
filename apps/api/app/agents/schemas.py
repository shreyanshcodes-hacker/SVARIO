"""Pydantic schemas for Stage 4 AI Agent, Intent Classification, Tools, Context & Orchestration.

Security Principles:
- All tool input schemas enforce `ConfigDict(extra="forbid")` and NEVER accept
  `organization_id` or `business_id` from the AI model; identity is always resolved
  and enforced by the FastAPI backend.
- Recognising `booking_intent`, `rescheduling_intent`, or `cancellation_intent`
  never executes a booking in Stage 4 (`booking_created` is always `False`).
- `request_human_escalation` explicitly reports `notification_delivered: False`
  so the AI never claims a human has already been contacted live.
"""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field, field_validator
from app.modules.onboarding.schemas import LanguageCode, WeekdayHoursItem
from app.modules.organizations.schemas import OrganizationIndustry
from app.modules.voice.schemas import VoiceAccessMode


class AgentIntent(str, Enum):
    """Stage 4 canonical intent taxonomy."""

    GREETING = "greeting"
    BUSINESS_INFORMATION = "business_information"
    OPENING_HOURS = "opening_hours"
    LOCATION = "location"
    SERVICES_ENQUIRY = "services_enquiry"
    PRICING_ENQUIRY = "pricing_enquiry"
    SPECIALITY_ENQUIRY = "speciality_enquiry"
    DEPARTMENT_ENQUIRY = "department_enquiry"
    BOOKING_INTENT = "booking_intent"
    RESCHEDULING_INTENT = "rescheduling_intent"
    CANCELLATION_INTENT = "cancellation_intent"
    HUMAN_SUPPORT = "human_support"
    EMERGENCY_INTENT = "emergency_intent"
    UNKNOWN = "unknown"


class SafetyFlag(str, Enum):
    """Safety and policy flags raised during intent & input inspection."""

    CLINICAL_DIAGNOSIS_REQUEST = "clinical_diagnosis_request"
    PRESCRIPTION_OR_MEDICATION_REQUEST = "prescription_or_medication_request"
    TREATMENT_RECOMMENDATION_REQUEST = "treatment_recommendation_request"
    MEDICAL_EMERGENCY_DETECTED = "medical_emergency_detected"
    SENSITIVE_MEDICAL_HISTORY_DISCLOSED = "sensitive_medical_history_disclosed"
    PROMPT_INJECTION_OR_POLICY_BYPASS = "prompt_injection_or_policy_bypass"


class AgentToolName(str, Enum):
    """Approved Stage 4 & Stage 5 backend-executed agent tools."""

    GET_BUSINESS_PROFILE = "get_business_profile"
    GET_BUSINESS_HOURS = "get_business_hours"
    SEARCH_BUSINESS_KNOWLEDGE = "search_business_knowledge"
    SAVE_CONVERSATION_SUMMARY = "save_conversation_summary"
    REQUEST_HUMAN_ESCALATION = "request_human_escalation"
    # Stage 5 Salon Workflow Tools
    GET_SALON_SERVICES = "get_salon_services"
    GET_SALON_STAFF = "get_salon_staff"
    CHECK_SALON_AVAILABILITY = "check_salon_availability"
    CREATE_SALON_APPOINTMENT = "create_salon_appointment"
    RESCHEDULE_SALON_APPOINTMENT = "reschedule_salon_appointment"
    CANCEL_SALON_APPOINTMENT = "cancel_salon_appointment"
    # Stage 6 Clinic Workflow Tools
    GET_CLINIC_INFORMATION = "get_clinic_information"
    GET_CLINIC_DEPARTMENTS = "get_clinic_departments"
    GET_CLINIC_DOCTORS = "get_clinic_doctors"
    GET_CLINIC_SPECIALITIES = "get_clinic_specialities"
    GET_CLINIC_CONSULTATION_TYPES = "get_clinic_consultation_types"
    CHECK_CLINIC_AVAILABILITY = "check_clinic_availability"
    CREATE_CLINIC_APPOINTMENT = "create_clinic_appointment"
    RESCHEDULE_CLINIC_APPOINTMENT = "reschedule_clinic_appointment"
    CANCEL_CLINIC_APPOINTMENT = "cancel_clinic_appointment"
    REQUEST_CLINIC_HUMAN_ESCALATION = "request_clinic_human_escalation"


class EscalationUrgency(str, Enum):
    """Controlled urgency levels for human escalation requests."""

    STANDARD = "standard"
    PRIORITY = "priority"
    CLINICAL_STAFF = "clinical_staff"
    EMERGENCY_REDIRECTED = "emergency_redirected"


class IntentClassificationResult(BaseModel):
    """Validated output of the Stage 4 intent recognition engine."""

    model_config = ConfigDict(extra="forbid")

    intent: AgentIntent
    confidence: float = Field(..., ge=0.0, le=1.0)
    detected_language: LanguageCode = Field(default=LanguageCode.ENGLISH)
    extracted_entities: Dict[str, Any] = Field(default_factory=dict)
    missing_information: List[str] = Field(default_factory=list)
    requires_tool: bool = Field(default=False)
    recommended_tool: Optional[AgentToolName] = None
    requires_human: bool = Field(default=False)
    safety_flags: List[SafetyFlag] = Field(default_factory=list)


class SourceMetadata(BaseModel):
    """Internal provenance metadata returned by knowledge/profile/hours tools."""

    organization_id: UUID
    business_id: UUID
    source_tables: List[str]
    retrieved_at: datetime


# ============================================================================
# Phase 4F — Structured Agent Tool Input & Output Schemas
# ============================================================================


class GetBusinessProfileToolInput(BaseModel):
    """Input for `get_business_profile` (organization/business resolved by backend)."""

    model_config = ConfigDict(extra="forbid")


class GetBusinessProfileToolOutput(BaseModel):
    """Verified output for `get_business_profile`."""

    business_name: str
    industry: OrganizationIndustry
    description: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    website: Optional[str] = None
    address_summary: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    country: Optional[str] = None
    postal_code: Optional[str] = None
    timezone: str
    primary_language: LanguageCode
    supported_languages: List[LanguageCode]
    assistant_name: str
    assistant_greeting: str
    assistant_personality: str
    assistant_response_style: str
    assistant_enabled: bool
    source_metadata: SourceMetadata


class GetBusinessHoursToolInput(BaseModel):
    """Input for `get_business_hours`."""

    model_config = ConfigDict(extra="forbid")

    weekday: Optional[int] = Field(
        default=None,
        ge=0,
        le=6,
        description="Optional weekday filter (0=Sunday .. 6=Saturday).",
    )


class GetBusinessHoursToolOutput(BaseModel):
    """Verified output for `get_business_hours`."""

    business_name: str
    timezone: str
    schedule: List[WeekdayHoursItem]
    source_metadata: SourceMetadata


class SearchBusinessKnowledgeToolInput(BaseModel):
    """Input for `search_business_knowledge`."""

    model_config = ConfigDict(extra="forbid")

    query: str = Field(..., min_length=2, max_length=300)
    category: Optional[str] = Field(default=None, max_length=80)

    @field_validator("query")
    @classmethod
    def clean_query(cls, value: str) -> str:
        trimmed = value.strip()
        if len(trimmed) < 2:
            raise ValueError("Search query must contain at least 2 characters.")
        return trimmed


class KnowledgeMatchItem(BaseModel):
    """Single verified knowledge match from active FAQs or business configuration."""

    source_type: str = Field(
        ..., description="'business_faq' | 'business_profile' | 'business_hours'"
    )
    record_id: str
    category: str
    question_or_topic: str
    verified_answer: str
    relevance_score: float = Field(..., ge=0.0, le=1.0)


class SearchBusinessKnowledgeToolOutput(BaseModel):
    """Verified output for `search_business_knowledge`."""

    query: str
    matches: List[KnowledgeMatchItem]
    total_matches: int
    has_verified_answer: bool
    confidence: float = Field(..., ge=0.0, le=1.0)
    fallback_directive: Optional[str] = None
    source_metadata: SourceMetadata


class SaveConversationSummaryToolInput(BaseModel):
    """Input for `save_conversation_summary`."""

    model_config = ConfigDict(extra="forbid")

    summary_text: str = Field(..., min_length=5, max_length=1500)
    primary_intent: AgentIntent = Field(default=AgentIntent.UNKNOWN)
    detected_language: LanguageCode = Field(default=LanguageCode.ENGLISH)
    booking_preferences: Dict[str, str] = Field(default_factory=dict)

    @field_validator("summary_text")
    @classmethod
    def clean_summary(cls, value: str) -> str:
        trimmed = value.strip()
        if len(trimmed) < 5:
            raise ValueError("summary_text must contain at least 5 characters.")
        return trimmed


class SaveConversationSummaryToolOutput(BaseModel):
    """Verified output for `save_conversation_summary`."""

    saved: bool
    persistence_mode: str
    summary_id: Optional[UUID] = None
    session_id: str
    redacted_summary: str
    booking_preferences_captured: Dict[str, str] = Field(default_factory=dict)
    booking_created: bool = False
    audit_log_id: Optional[UUID] = None


class RequestHumanEscalationToolInput(BaseModel):
    """Input for `request_human_escalation`."""

    model_config = ConfigDict(extra="forbid")

    reason: str = Field(..., min_length=3, max_length=300)
    summary: str = Field(..., min_length=5, max_length=1000)
    urgency: EscalationUrgency = Field(default=EscalationUrgency.STANDARD)
    conversation_reference: Optional[str] = Field(default=None, max_length=120)

    @field_validator("reason", "summary")
    @classmethod
    def strip_text_fields(cls, value: str) -> str:
        trimmed = value.strip()
        if len(trimmed) < 3:
            raise ValueError("Escalation reason and summary cannot be empty.")
        return trimmed


class RequestHumanEscalationToolOutput(BaseModel):
    """Verified output for `request_human_escalation`."""

    accepted: bool
    escalation_reference: Optional[str] = None
    status: str
    urgency: EscalationUrgency
    preferred_method: Optional[str] = None
    contact_name: Optional[str] = None
    contact_phone: Optional[str] = None
    contact_email: Optional[str] = None
    escalation_instructions: Optional[str] = None
    notification_delivered: bool = False
    customer_message_directive: str
    audit_log_id: Optional[UUID] = None


# ============================================================================
# Stage 5 Salon Workflow Agent Tool Schemas
# ============================================================================


class GetSalonServicesToolInput(BaseModel):
    """Input for `get_salon_services` tool."""

    model_config = ConfigDict(extra="forbid")

    category: Optional[str] = Field(default=None, max_length=80)
    is_active: Optional[bool] = Field(default=True)


class SalonServiceSummaryItem(BaseModel):
    service_id: str
    name: str
    category: str
    price: float
    currency: str
    duration_minutes: int


class GetSalonServicesToolOutput(BaseModel):
    """Output for `get_salon_services` tool."""

    services: List[SalonServiceSummaryItem]
    count: int
    categories: List[str]


class GetSalonStaffToolInput(BaseModel):
    """Input for `get_salon_staff` tool."""

    model_config = ConfigDict(extra="forbid")

    service_id: Optional[str] = Field(default=None)


class SalonStaffSummaryItem(BaseModel):
    staff_id: str
    name: str
    role: str
    assigned_service_names: List[str]


class GetSalonStaffToolOutput(BaseModel):
    """Output for `get_salon_staff` tool."""

    staff: List[SalonStaffSummaryItem]
    count: int


class CheckSalonAvailabilityToolInput(BaseModel):
    """Input for `check_salon_availability` tool."""

    model_config = ConfigDict(extra="forbid")

    service_id: str = Field(..., description="ID of the salon service (from get_salon_services)")
    requested_date: str = Field(..., description="Date in YYYY-MM-DD format (e.g. 2026-11-25)")
    staff_id: Optional[str] = Field(default=None, description="Optional preferred staff ID")
    requested_time: Optional[str] = Field(
        default=None,
        description="Optional requested time (e.g. '14:00' or '2:00 PM') to verify directly against available slots.",
    )


class SalonSlotSummaryItem(BaseModel):
    start_time: str
    end_time: str
    staff_id: str
    staff_name: str
    staff_role: str


class CheckSalonAvailabilityToolOutput(BaseModel):
    """Output for `check_salon_availability` tool."""

    service_name: str
    duration_minutes: int
    requested_date: str
    timezone: str
    is_business_closed: bool
    closure_reason: Optional[str] = None
    availability_status: str = "AVAILABLE"
    status_reason: Optional[str] = None
    requested_time: Optional[str] = None
    requested_time_available: Optional[bool] = None
    available_slots: List[SalonSlotSummaryItem]
    total_slots_available: int


class CreateSalonAppointmentToolInput(BaseModel):
    """Input for `create_salon_appointment` tool."""

    model_config = ConfigDict(extra="forbid")

    service_id: str = Field(..., description="ID of the selected salon service")
    appointment_date: str = Field(..., description="Date in YYYY-MM-DD format")
    start_time: str = Field(..., description="Start time in HH:MM format (from check_salon_availability)")
    customer_name: str = Field(..., min_length=2, max_length=120)
    customer_phone: str = Field(..., min_length=6, max_length=32)
    customer_email: Optional[str] = Field(default=None, max_length=160)
    staff_id: Optional[str] = Field(default=None, description="Optional chosen staff ID")
    notes: Optional[str] = Field(default=None, max_length=500)
    idempotency_key: Optional[str] = Field(default=None, max_length=128)


class CreateSalonAppointmentToolOutput(BaseModel):
    """Output for `create_salon_appointment` tool."""

    booking_confirmed: bool
    booking_reference: str
    service_name: str
    staff_name: str
    appointment_date: str
    start_time: str
    end_time: str
    duration_minutes: int
    price: float
    currency: str
    customer_name: str
    customer_phone: str
    timezone: str
    message: str


class RescheduleSalonAppointmentToolInput(BaseModel):
    """Input for `reschedule_salon_appointment` tool."""

    model_config = ConfigDict(extra="forbid")

    appointment_id: str = Field(..., description="Appointment ID or reference to reschedule")
    new_date: str = Field(..., description="New date in YYYY-MM-DD format")
    new_start_time: str = Field(..., description="New start time in HH:MM format")
    new_staff_id: Optional[str] = None
    notes: Optional[str] = None


class RescheduleSalonAppointmentToolOutput(BaseModel):
    """Output for `reschedule_salon_appointment` tool."""

    reschedule_confirmed: bool
    booking_reference: str
    service_name: str
    staff_name: str
    new_date: str
    new_start_time: str
    new_end_time: str
    message: str


class CancelSalonAppointmentToolInput(BaseModel):
    """Input for `cancel_salon_appointment` tool."""

    model_config = ConfigDict(extra="forbid")

    appointment_id: str = Field(..., description="Appointment ID or reference to cancel")
    cancellation_reason: Optional[str] = Field(default=None, max_length=300)


class CancelSalonAppointmentToolOutput(BaseModel):
    """Output for `cancel_salon_appointment` tool."""

    cancellation_confirmed: bool
    booking_reference: str
    service_name: str
    appointment_date: str
    start_time: str
    message: str


# ============================================================================
# Phase 4E, 4G & 4I — Conversation Context, Realtime Tool Execution & Turn APIs
# ============================================================================


class SessionConversationContext(BaseModel):
    """Session-scoped, tenant-isolated conversation context (Phase 4E)."""

    session_id: str
    organization_id: UUID
    business_id: UUID
    industry: OrganizationIndustry
    current_intent: AgentIntent = AgentIntent.UNKNOWN
    detected_language: LanguageCode = LanguageCode.ENGLISH
    extracted_entities: Dict[str, Any] = Field(default_factory=dict)
    previous_clarification_questions: List[str] = Field(default_factory=list)
    recent_user_queries: List[str] = Field(default_factory=list)
    conversation_summary: Optional[str] = None
    turn_count: int = 0
    tool_calls_in_current_turn: int = 0
    total_tool_calls: int = 0
    consecutive_low_confidence_turns: int = 0
    escalated: bool = False
    escalation_reference: Optional[str] = None
    escalation_status: Optional[str] = None
    last_updated_at: datetime


class AuditLogRecord(BaseModel):
    """Controlled audit log entry written for important Stage 4 agent actions."""

    id: UUID
    organization_id: UUID
    business_id: UUID
    session_id: str
    actor_user_id: Optional[UUID] = None
    action: str
    target_type: str
    target_id: str
    metadata: Dict[str, Any] = Field(default_factory=dict)
    created_at: datetime


class VoiceToolExecutionRequest(BaseModel):
    """Request from browser WebRTC client (`oai-events` function call) to execute an agent tool."""

    model_config = ConfigDict(extra="forbid")

    session_id: str = Field(..., min_length=3, max_length=128)
    organization_id: UUID
    business_id: Optional[UUID] = None
    access_mode: VoiceAccessMode = Field(default=VoiceAccessMode.ORGANIZATION_MEMBER)
    public_access_token: Optional[str] = Field(default=None, max_length=2048)
    call_id: str = Field(..., min_length=2, max_length=128)
    tool_name: AgentToolName
    arguments: Dict[str, Any] = Field(default_factory=dict)


class VoiceToolExecutionResponse(BaseModel):
    """Structured tool execution result formatted for OpenAI Realtime `function_call_output`."""

    session_id: str
    call_id: str
    tool_name: AgentToolName
    status: str = Field(..., description="'succeeded' | 'rejected' | 'error'")
    output: Dict[str, Any]
    escalation_triggered: bool = False
    escalation_reference: Optional[str] = None
    detected_language: LanguageCode = LanguageCode.ENGLISH


class AgentTurnRequest(BaseModel):
    """Request to run a full controlled Stage 4 conversational turn (`POST /api/v1/agent/turns`)."""

    model_config = ConfigDict(extra="forbid")

    session_id: str = Field(..., min_length=3, max_length=128)
    organization_id: UUID
    business_id: Optional[UUID] = None
    access_mode: VoiceAccessMode = Field(default=VoiceAccessMode.ORGANIZATION_MEMBER)
    public_access_token: Optional[str] = Field(default=None, max_length=2048)
    user_input: str = Field(..., min_length=1, max_length=1500)
    preferred_language: Optional[LanguageCode] = None

    @field_validator("user_input")
    @classmethod
    def clean_user_input(cls, value: str) -> str:
        trimmed = value.strip()
        if not trimmed:
            raise ValueError("user_input cannot be empty or whitespace only.")
        return trimmed


class ExecutedToolCallSummary(BaseModel):
    """Summary of a validated backend tool call executed during a turn."""

    tool_name: AgentToolName
    status: str
    output: Dict[str, Any]


class AgentTurnResponse(BaseModel):
    """Structured response from `AgentOrchestrator.process_turn`."""

    session_id: str
    organization_id: UUID
    business_id: UUID
    industry: OrganizationIndustry
    intent_result: IntentClassificationResult
    tool_calls: List[ExecutedToolCallSummary] = Field(default_factory=list)
    spoken_response: str
    response_language: LanguageCode
    clarification_question: Optional[str] = None
    escalated: bool = False
    escalation_reference: Optional[str] = None
    escalation_status: Optional[str] = None
    emergency_guidance_issued: bool = False
    booking_created: bool = False
    context_snapshot: SessionConversationContext


# ============================================================================
# Stage 6 Clinic Workflow Tool Schemas
# ============================================================================


class GetClinicInformationToolInput(BaseModel):
    model_config = ConfigDict(extra="forbid")


class GetClinicInformationToolOutput(BaseModel):
    clinic_name: str
    description: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    address_summary: Optional[str] = None
    timezone: str
    operating_hours: List[WeekdayHoursItem]
    supported_languages: List[LanguageCode]


class GetClinicDepartmentsToolInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    active_only: bool = True


class ClinicDepartmentSummaryItem(BaseModel):
    department_id: str
    name: str
    description: Optional[str] = None


class GetClinicDepartmentsToolOutput(BaseModel):
    departments: List[ClinicDepartmentSummaryItem]
    total_count: int


class GetClinicSpecialitiesToolInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    active_only: bool = True


class ClinicSpecialitySummaryItem(BaseModel):
    speciality_id: str
    name: str
    description: Optional[str] = None


class GetClinicSpecialitiesToolOutput(BaseModel):
    specialities: List[ClinicSpecialitySummaryItem]
    total_count: int


class GetClinicDoctorsToolInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    department_id: Optional[UUID] = None
    speciality_id: Optional[UUID] = None
    active_only: bool = True


class ClinicDoctorSummaryItem(BaseModel):
    doctor_id: str
    display_name: str
    professional_title: Optional[str] = None
    languages: List[str]
    department_ids: List[str]
    speciality_ids: List[str]
    consultation_type_ids: List[str]


class GetClinicDoctorsToolOutput(BaseModel):
    doctors: List[ClinicDoctorSummaryItem]
    total_count: int


class GetClinicConsultationTypesToolInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    active_only: bool = True


class ClinicConsultationTypeSummaryItem(BaseModel):
    consultation_type_id: str
    name: str
    description: Optional[str] = None
    duration_minutes: int
    consultation_mode: str
    fee_amount: Optional[float] = None
    currency_code: Optional[str] = None


class GetClinicConsultationTypesToolOutput(BaseModel):
    consultation_types: List[ClinicConsultationTypeSummaryItem]
    total_count: int


class CheckClinicAvailabilityToolInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    consultation_type_id: UUID
    target_date: str = Field(..., description="YYYY-MM-DD format")
    doctor_id: Optional[UUID] = None
    department_id: Optional[UUID] = None
    speciality_id: Optional[UUID] = None


class ClinicSlotSummaryItem(BaseModel):
    doctor_id: str
    doctor_name: str
    starts_at: str
    ends_at: str
    timezone: str


class CheckClinicAvailabilityToolOutput(BaseModel):
    target_date: str
    timezone: str
    duration_minutes: int
    available_slots: List[ClinicSlotSummaryItem]
    total_slots: int


class CreateClinicAppointmentToolInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    doctor_id: UUID
    consultation_type_id: UUID
    department_id: Optional[UUID] = None
    patient_display_name: str = Field(..., min_length=2, max_length=120)
    patient_contact: str = Field(..., min_length=5, max_length=80)
    starts_at: str = Field(..., description="ISO-8601 datetime with timezone")
    idempotency_key: Optional[str] = None


class CreateClinicAppointmentToolOutput(BaseModel):
    booked: bool
    booking_reference: Optional[str] = None
    appointment_id: Optional[str] = None
    doctor_name: Optional[str] = None
    consultation_type_name: Optional[str] = None
    starts_at: Optional[str] = None
    ends_at: Optional[str] = None
    timezone: Optional[str] = None
    status: str
    message: str


class RescheduleClinicAppointmentToolInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    booking_reference: str = Field(..., min_length=4, max_length=40)
    patient_contact_verification: str = Field(..., min_length=4, max_length=80)
    new_starts_at: str = Field(..., description="ISO-8601 datetime with timezone")
    new_doctor_id: Optional[UUID] = None


class RescheduleClinicAppointmentToolOutput(BaseModel):
    rescheduled: bool
    booking_reference: str
    new_starts_at: Optional[str] = None
    new_ends_at: Optional[str] = None
    doctor_name: Optional[str] = None
    status: str
    message: str


class CancelClinicAppointmentToolInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    booking_reference: str = Field(..., min_length=4, max_length=40)
    patient_contact_verification: str = Field(..., min_length=4, max_length=80)
    reason: Optional[str] = Field(default=None, max_length=250)


class CancelClinicAppointmentToolOutput(BaseModel):
    cancelled: bool
    booking_reference: str
    status: str
    message: str


class RequestClinicHumanEscalationToolInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    reason: str = Field(..., min_length=3, max_length=250)
    summary: str = Field(..., min_length=3, max_length=1000)
    urgency: EscalationUrgency = EscalationUrgency.STANDARD

