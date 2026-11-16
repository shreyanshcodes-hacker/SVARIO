"""Stage 4 & Stage 5 Structured Agent Tools (`apps/api/app/agents/tools`)."""

from app.agents.tools.business_hours import execute_get_business_hours
from app.agents.tools.business_profile import execute_get_business_profile
from app.agents.tools.conversation_summary import execute_save_conversation_summary
from app.agents.tools.escalation import execute_request_human_escalation
from app.agents.tools.knowledge_search import execute_search_business_knowledge
from app.agents.tools.clinic_tools import (
    execute_cancel_clinic_appointment,
    execute_check_clinic_availability,
    execute_create_clinic_appointment,
    execute_get_clinic_consultation_types,
    execute_get_clinic_departments,
    execute_get_clinic_doctors,
    execute_get_clinic_information,
    execute_get_clinic_specialities,
    execute_request_clinic_human_escalation,
    execute_reschedule_clinic_appointment,
)
from app.agents.tools.salon_tools import (
    execute_cancel_salon_appointment,
    execute_check_salon_availability,
    execute_create_salon_appointment,
    execute_get_salon_services,
    execute_get_salon_staff,
    execute_reschedule_salon_appointment,
)

__all__ = [
    "execute_get_business_hours",
    "execute_get_business_profile",
    "execute_request_human_escalation",
    "execute_save_conversation_summary",
    "execute_search_business_knowledge",
    "execute_get_salon_services",
    "execute_get_salon_staff",
    "execute_check_salon_availability",
    "execute_create_salon_appointment",
    "execute_reschedule_salon_appointment",
    "execute_cancel_salon_appointment",
    "execute_get_clinic_information",
    "execute_get_clinic_departments",
    "execute_get_clinic_doctors",
    "execute_get_clinic_specialities",
    "execute_get_clinic_consultation_types",
    "execute_check_clinic_availability",
    "execute_create_clinic_appointment",
    "execute_reschedule_clinic_appointment",
    "execute_cancel_clinic_appointment",
    "execute_request_clinic_human_escalation",
]
