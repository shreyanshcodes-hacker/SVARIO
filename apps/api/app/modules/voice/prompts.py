"""Server-authoritative system instruction builder for Voice Sessions.

Delegates directly to Stage 4's modular `build_stage4_agent_instructions` so there
is a single unified voice-session instruction architecture across Stage 3 and Stage 4.
"""

from app.agents.instructions import build_stage4_agent_instructions
from app.modules.onboarding.schemas import OnboardingBundleResponse


def build_safe_realtime_instructions(bundle: OnboardingBundleResponse) -> str:
    """Compose deterministic, server-authoritative Realtime instructions."""
    return build_stage4_agent_instructions(bundle)
