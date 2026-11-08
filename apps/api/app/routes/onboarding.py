"""Organization-scoped Stage 2 Business Onboarding routes for Svario API."""

from typing import List
from uuid import UUID
from fastapi import APIRouter, Depends, Response, status
from app.core.auth import AuthenticatedUser, get_current_user
from app.modules.onboarding.schemas import (
    AssistantSettingsResponse,
    AssistantSettingsUpdateRequest,
    BusinessFaqCreateRequest,
    BusinessFaqResponse,
    BusinessFaqUpdateRequest,
    BusinessHoursResponse,
    BusinessHoursUpdateRequest,
    BusinessLanguagesResponse,
    BusinessLanguagesUpdateRequest,
    BusinessProfileResponse,
    BusinessProfileUpdateRequest,
    EscalationSettingsResponse,
    EscalationSettingsUpdateRequest,
    OnboardingBundleResponse,
    OnboardingProgressResponse,
    OnboardingProgressUpdateRequest,
    UpdateIndustryRequest,
)
from app.modules.onboarding.service import OnboardingService, get_onboarding_service
from app.modules.organizations.schemas import OrganizationDetailResponse

router = APIRouter(
    prefix="/api/v1/organizations/{organization_id}/onboarding",
    tags=["Business Onboarding (Stage 2)"],
)


@router.get(
    "",
    response_model=OnboardingBundleResponse,
    summary="Get Complete Organization Onboarding State",
)
async def get_onboarding_bundle(
    organization_id: UUID,
    current_user: AuthenticatedUser = Depends(get_current_user),
    service: OnboardingService = Depends(get_onboarding_service),
) -> OnboardingBundleResponse:
    """Return full Stage 2 onboarding state for an organization member."""
    return await service.get_onboarding_bundle(
        actor=current_user, organization_id=organization_id
    )


@router.put(
    "/industry",
    response_model=OrganizationDetailResponse,
    summary="Confirm or Update Organization Industry (Owner/Admin Only)",
)
async def update_organization_industry(
    organization_id: UUID,
    payload: UpdateIndustryRequest,
    current_user: AuthenticatedUser = Depends(get_current_user),
    service: OnboardingService = Depends(get_onboarding_service),
) -> OrganizationDetailResponse:
    """Update organization industry (salon, clinic, hospital) after verifying owner/admin role."""
    return await service.update_industry(
        actor=current_user, organization_id=organization_id, payload=payload
    )


@router.get(
    "/profile",
    response_model=BusinessProfileResponse,
    summary="Get Business Profile",
)
async def get_business_profile(
    organization_id: UUID,
    current_user: AuthenticatedUser = Depends(get_current_user),
    service: OnboardingService = Depends(get_onboarding_service),
) -> BusinessProfileResponse:
    """Return business profile for the organization."""
    return await service.get_profile(
        actor=current_user, organization_id=organization_id
    )


@router.put(
    "/profile",
    response_model=BusinessProfileResponse,
    summary="Create or Update Business Profile (Owner/Admin Only)",
)
async def update_business_profile(
    organization_id: UUID,
    payload: BusinessProfileUpdateRequest,
    current_user: AuthenticatedUser = Depends(get_current_user),
    service: OnboardingService = Depends(get_onboarding_service),
) -> BusinessProfileResponse:
    """Create or update the organization's business profile."""
    return await service.update_profile(
        actor=current_user, organization_id=organization_id, payload=payload
    )


@router.get(
    "/hours",
    response_model=BusinessHoursResponse,
    summary="Get Weekly Business Hours",
)
async def get_business_hours(
    organization_id: UUID,
    current_user: AuthenticatedUser = Depends(get_current_user),
    service: OnboardingService = Depends(get_onboarding_service),
) -> BusinessHoursResponse:
    """Return weekly operating hours for the organization's business."""
    return await service.get_hours(
        actor=current_user, organization_id=organization_id
    )


@router.put(
    "/hours",
    response_model=BusinessHoursResponse,
    summary="Update Weekly Business Hours (Owner/Admin Only)",
)
async def update_business_hours(
    organization_id: UUID,
    payload: BusinessHoursUpdateRequest,
    current_user: AuthenticatedUser = Depends(get_current_user),
    service: OnboardingService = Depends(get_onboarding_service),
) -> BusinessHoursResponse:
    """Validate and persist weekly operating hours for the organization's business."""
    return await service.update_hours(
        actor=current_user, organization_id=organization_id, payload=payload
    )


@router.get(
    "/languages",
    response_model=BusinessLanguagesResponse,
    summary="Get Business Languages",
)
async def get_business_languages(
    organization_id: UUID,
    current_user: AuthenticatedUser = Depends(get_current_user),
    service: OnboardingService = Depends(get_onboarding_service),
) -> BusinessLanguagesResponse:
    """Return primary and supported languages for the business."""
    return await service.get_languages(
        actor=current_user, organization_id=organization_id
    )


@router.put(
    "/languages",
    response_model=BusinessLanguagesResponse,
    summary="Update Business Languages (Owner/Admin Only)",
)
async def update_business_languages(
    organization_id: UUID,
    payload: BusinessLanguagesUpdateRequest,
    current_user: AuthenticatedUser = Depends(get_current_user),
    service: OnboardingService = Depends(get_onboarding_service),
) -> BusinessLanguagesResponse:
    """Persist primary and supported languages (en, hi, hinglish)."""
    return await service.update_languages(
        actor=current_user, organization_id=organization_id, payload=payload
    )


@router.get(
    "/assistant",
    response_model=AssistantSettingsResponse,
    summary="Get AI Voice Assistant Configuration",
)
async def get_assistant_settings(
    organization_id: UUID,
    current_user: AuthenticatedUser = Depends(get_current_user),
    service: OnboardingService = Depends(get_onboarding_service),
) -> AssistantSettingsResponse:
    """Return AI voice assistant configuration settings."""
    return await service.get_assistant(
        actor=current_user, organization_id=organization_id
    )


@router.put(
    "/assistant",
    response_model=AssistantSettingsResponse,
    summary="Update AI Voice Assistant Configuration (Owner/Admin Only)",
)
async def update_assistant_settings(
    organization_id: UUID,
    payload: AssistantSettingsUpdateRequest,
    current_user: AuthenticatedUser = Depends(get_current_user),
    service: OnboardingService = Depends(get_onboarding_service),
) -> AssistantSettingsResponse:
    """Update AI voice assistant name, greeting, personality, and response style."""
    return await service.update_assistant(
        actor=current_user, organization_id=organization_id, payload=payload
    )


@router.get(
    "/faqs",
    response_model=List[BusinessFaqResponse],
    summary="List Business FAQs",
)
async def list_business_faqs(
    organization_id: UUID,
    current_user: AuthenticatedUser = Depends(get_current_user),
    service: OnboardingService = Depends(get_onboarding_service),
) -> List[BusinessFaqResponse]:
    """List FAQs for the organization ordered by sort_order."""
    return await service.list_faqs(
        actor=current_user, organization_id=organization_id
    )


@router.post(
    "/faqs",
    response_model=BusinessFaqResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create Business FAQ (Owner/Admin Only)",
)
async def create_business_faq(
    organization_id: UUID,
    payload: BusinessFaqCreateRequest,
    current_user: AuthenticatedUser = Depends(get_current_user),
    service: OnboardingService = Depends(get_onboarding_service),
) -> BusinessFaqResponse:
    """Create a new FAQ entry for the organization's business."""
    return await service.create_faq(
        actor=current_user, organization_id=organization_id, payload=payload
    )


@router.put(
    "/faqs/{faq_id}",
    response_model=BusinessFaqResponse,
    summary="Update Business FAQ (Owner/Admin Only)",
)
async def update_business_faq(
    organization_id: UUID,
    faq_id: UUID,
    payload: BusinessFaqUpdateRequest,
    current_user: AuthenticatedUser = Depends(get_current_user),
    service: OnboardingService = Depends(get_onboarding_service),
) -> BusinessFaqResponse:
    """Update question, answer, category, sort_order, or active state of an FAQ."""
    return await service.update_faq(
        actor=current_user,
        organization_id=organization_id,
        faq_id=faq_id,
        payload=payload,
    )


@router.delete(
    "/faqs/{faq_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete Business FAQ (Owner/Admin Only)",
)
async def delete_business_faq(
    organization_id: UUID,
    faq_id: UUID,
    current_user: AuthenticatedUser = Depends(get_current_user),
    service: OnboardingService = Depends(get_onboarding_service),
) -> Response:
    """Delete an FAQ entry belonging to the organization."""
    await service.delete_faq(
        actor=current_user, organization_id=organization_id, faq_id=faq_id
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get(
    "/escalation",
    response_model=EscalationSettingsResponse,
    summary="Get Human Escalation Settings",
)
async def get_escalation_settings(
    organization_id: UUID,
    current_user: AuthenticatedUser = Depends(get_current_user),
    service: OnboardingService = Depends(get_onboarding_service),
) -> EscalationSettingsResponse:
    """Return human escalation configuration for the organization."""
    return await service.get_escalation(
        actor=current_user, organization_id=organization_id
    )


@router.put(
    "/escalation",
    response_model=EscalationSettingsResponse,
    summary="Update Human Escalation Settings (Owner/Admin Only)",
)
async def update_escalation_settings(
    organization_id: UUID,
    payload: EscalationSettingsUpdateRequest,
    current_user: AuthenticatedUser = Depends(get_current_user),
    service: OnboardingService = Depends(get_onboarding_service),
) -> EscalationSettingsResponse:
    """Update human escalation contact details, preferred method, and instructions."""
    return await service.update_escalation(
        actor=current_user, organization_id=organization_id, payload=payload
    )


@router.get(
    "/progress",
    response_model=OnboardingProgressResponse,
    summary="Get Onboarding Progress",
)
async def get_onboarding_progress(
    organization_id: UUID,
    current_user: AuthenticatedUser = Depends(get_current_user),
    service: OnboardingService = Depends(get_onboarding_service),
) -> OnboardingProgressResponse:
    """Return current onboarding step and completed steps."""
    return await service.get_progress(
        actor=current_user, organization_id=organization_id
    )


@router.put(
    "/progress",
    response_model=OnboardingProgressResponse,
    summary="Save Onboarding Progress & Completion State (Owner/Admin Only)",
)
async def update_onboarding_progress(
    organization_id: UUID,
    payload: OnboardingProgressUpdateRequest,
    current_user: AuthenticatedUser = Depends(get_current_user),
    service: OnboardingService = Depends(get_onboarding_service),
) -> OnboardingProgressResponse:
    """Save current step, completed steps, or final onboarding completion."""
    return await service.update_progress(
        actor=current_user, organization_id=organization_id, payload=payload
    )
