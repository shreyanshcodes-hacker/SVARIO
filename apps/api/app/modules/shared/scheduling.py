"""Shared Scheduling Engine Boundary (Stage 0 Foundation).

Defines the architectural boundary for availability resolution, resource locking,
stylist/practitioner/department slot matching, and conflict prevention.
No appointment booking logic or database persistence is implemented in Stage 0.
"""

from app.modules.shared.contracts import SharedSubsystemBoundary

SCHEDULING_SUBSYSTEM_BOUNDARY = SharedSubsystemBoundary(
    subsystem_id="scheduling",
    name="Shared Scheduling & Availability Boundary",
    purpose=(
        "Abstracts calendar slots, practitioner/resource constraints, and booking "
        "state transitions behind a unified multi-tenant interface."
    ),
    planned_provider="Supabase PostgreSQL + Realtime",
)
