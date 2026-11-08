"""Shared Voice Subsystem Boundary (Stage 0 Foundation).

Defines the architectural boundary for real-time audio streaming, speech-to-speech
turn management, and telephony/WebRTC session orchestration.
No OpenAI Realtime API calls are implemented in Stage 0.
"""

from app.modules.shared.contracts import SharedSubsystemBoundary

VOICE_SUBSYSTEM_BOUNDARY = SharedSubsystemBoundary(
    subsystem_id="voice",
    name="Shared Voice Runtime Boundary",
    purpose=(
        "Manages low-latency bidirectional audio streams, barge-in handling, "
        "and session lifecycle across all industry voice agents."
    ),
    planned_provider="OpenAI Realtime API",
)
