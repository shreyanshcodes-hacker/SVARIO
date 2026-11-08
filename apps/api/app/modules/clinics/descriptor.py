"""Clinics vertical boundary definition.

Stage 0 Note:
Defines static module metadata and integration boundaries with shared voice, AI,
scheduling, and notification subsystems. No active clinic workflows are implemented here.
"""

from app.modules.shared.contracts import IndustryDomain, IndustryModuleDescriptor

CLINICS_MODULE_DESCRIPTOR = IndustryModuleDescriptor(
    domain=IndustryDomain.CLINICS,
    title="Outpatient & Specialty Clinics",
    subtitle="Structured Patient Intake & Practitioner Desk Coordination",
    summary=(
        "Supports dental, dermatology, physiotherapy, and diagnostic clinics with "
        "calm patient communication, pre-visit instructions, and practitioner slot routing."
    ),
    voice_persona_focus="Empathetic, clear clinical coordinator with strict non-diagnostic guardrails.",
    planned_capabilities=[
        "First-visit vs. follow-up consultation classification",
        "Practitioner specialty & clinic hours routing",
        "Pre-appointment preparation instruction delivery",
        "Urgent symptom detection & immediate staff transfer boundary",
    ],
)


class ClinicsModule:
    """Architectural boundary adapter for Clinic workflows."""

    def get_descriptor(self) -> IndustryModuleDescriptor:
        return CLINICS_MODULE_DESCRIPTOR
