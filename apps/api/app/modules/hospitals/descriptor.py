"""Hospitals vertical boundary definition.

Stage 0 Note:
Defines static module metadata and integration boundaries with shared voice, AI,
scheduling, and notification subsystems. No active hospital workflows are implemented here.
"""

from app.modules.shared.contracts import IndustryDomain, IndustryModuleDescriptor

HOSPITALS_MODULE_DESCRIPTOR = IndustryModuleDescriptor(
    domain=IndustryDomain.HOSPITALS,
    title="Hospitals & Multi-Specialty Centers",
    subtitle="24/7 Departmental Switchboard, OPD Navigation & Escalation Guardrails",
    summary=(
        "Designed for high-concurrency hospital front desks to route callers across "
        "OPD departments, visiting-hour queries, and emergency human handoff protocols."
    ),
    voice_persona_focus="Calm, authoritative, safety-first institutional voice switchboard operator.",
    planned_capabilities=[
        "Multi-department OPD & specialist directory navigation",
        "Emergency red-flag detection & zero-delay live operator transfer",
        "Visiting hours, admission desk & diagnostics FAQ resolution",
        "Multi-lingual caller greeting & departmental queue routing",
    ],
)


class HospitalsModule:
    """Architectural boundary adapter for Hospital workflows."""

    def get_descriptor(self) -> IndustryModuleDescriptor:
        return HOSPITALS_MODULE_DESCRIPTOR
