"""Salons vertical boundary definition.

Stage 0 Note:
Defines static module metadata and integration boundaries with shared voice, AI,
scheduling, and notification subsystems. No active salon workflows are implemented here.
"""

from app.modules.shared.contracts import IndustryDomain, IndustryModuleDescriptor

SALONS_MODULE_DESCRIPTOR = IndustryModuleDescriptor(
    domain=IndustryDomain.SALONS,
    title="Salons & Grooming Studios",
    subtitle="Concierge Voice Reception for High-Volume Beauty & Wellness Brands",
    summary=(
        "Handles inbound service inquiries, stylist preference matching, package duration "
        "consultation, and seamless front-desk call overflow."
    ),
    voice_persona_focus="Warm, brand-aligned hospitality concierge with stylist & treatment vocabulary.",
    planned_capabilities=[
        "Service menu & treatment duration inquiries",
        "Stylist/specialist tier selection boundaries",
        "Peak-hour call overflow & deposit policy guidance",
        "Rescheduling & cancellation window handling",
    ],
)


class SalonsModule:
    """Architectural boundary adapter for Salon workflows."""

    def get_descriptor(self) -> IndustryModuleDescriptor:
        return SALONS_MODULE_DESCRIPTOR
