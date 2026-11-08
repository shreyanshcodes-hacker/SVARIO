"""Shared Notification Dispatch Boundary (Stage 0 Foundation).

Defines the architectural boundary for post-call summaries, confirmation messages,
and staff handoff alerts.
No external messaging or WhatsApp/SMS integrations are implemented in Stage 0.
"""

from app.modules.shared.contracts import SharedSubsystemBoundary

NOTIFICATIONS_SUBSYSTEM_BOUNDARY = SharedSubsystemBoundary(
    subsystem_id="notifications",
    name="Shared Notification & Handoff Boundary",
    purpose=(
        "Routes structured call outcomes, follow-ups, and human-escalation alerts "
        "from industry workflows to configured communication channels."
    ),
    planned_provider="Event-driven Webhook & Messaging Adapters (Future Stages)",
)
