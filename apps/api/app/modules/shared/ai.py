"""Shared AI Orchestration Boundary (Stage 0 Foundation).

Defines the architectural boundary for industry-specific prompt assembly,
guardrail policies, intent classification, and tool-calling schemas.
No AI agent execution is implemented in Stage 0.
"""

from app.modules.shared.contracts import SharedSubsystemBoundary

AI_SUBSYSTEM_BOUNDARY = SharedSubsystemBoundary(
    subsystem_id="ai",
    name="Shared AI & Policy Engine Boundary",
    purpose=(
        "Composes domain-specific personas, safety guardrails, escalation rules, "
        "and structured tool contracts for Salons, Clinics, and Hospitals."
    ),
    planned_provider="OpenAI Realtime & Structured Outputs",
)
