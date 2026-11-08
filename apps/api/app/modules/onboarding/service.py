"""Domain service enforcing organization-scoped RBAC for Stage 2 Business Onboarding."""

from typing import List
from uuid import UUID
from fastapi import Depends, HTTPException, status
from app.core.auth import AuthenticatedUser
from app.core.config import Settings, get_settings
from app.modules.onboarding.repository import (
    InMemoryOnboardingRepository,
    OnboardingRepositoryProtocol,
    SupabaseRestOnboardingRepository,
)
from app.modules.onboarding.schemas import (
    INDUSTRY_FAQ_TEMPLATES,
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
    HealthcareSafeguardNotice,
    OnboardingBundleResponse,
    OnboardingProgressResponse,
    OnboardingProgressUpdateRequest,
    OnboardingStepId,
    UpdateIndustryRequest,
)
from app.modules.organizations.schemas import (
    OrganizationDetailResponse,
    OrganizationIndustry,
    OrganizationRole,
)
from app.modules.organizations.service import get_in_memory_organization_repository

_in_memory_onboarding_repo = InMemoryOnboardingRepository(
    org_repo=get_in_memory_organization_repository()
)


def get_onboarding_repository(
    settings: Settings = Depends(get_settings),
) -> OnboardingRepositoryProtocol:
    """Resolve the active Stage 2 onboarding repository."""
    if settings.is_live_supabase_configured:
        return SupabaseRestOnboardingRepository(settings=settings)
    return _in_memory_onboarding_repo


class OnboardingService:
    """Organization-scoped onboarding service with strict member & role verification."""

    def __init__(self, repository: OnboardingRepositoryProtocol) -> None:
        self._repo = repository

    async def _require_member(
        self, actor: AuthenticatedUser, organization_id: UUID
    ) -> OrganizationRole:
        role = await self._repo.get_member_role(
            actor=actor, organization_id=organization_id
        )
        if role is None:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied: you are not a member of this organization.",
            )
        return role

    async def _require_owner_or_admin(
        self, actor: AuthenticatedUser, organization_id: UUID
    ) -> OrganizationRole:
        role = await self._require_member(actor=actor, organization_id=organization_id)
        if role not in {OrganizationRole.OWNER, OrganizationRole.ADMIN}:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient permissions: only organization owners or admins may modify onboarding or business configuration.",
            )
        return role

    async def _record_step_completed(
        self,
        actor: AuthenticatedUser,
        organization_id: UUID,
        business_id: UUID,
        completed_step: OnboardingStepId,
        next_step: OnboardingStepId,
    ) -> OnboardingProgressResponse:
        current = await self._repo.get_onboarding_progress(
            actor=actor,
            organization_id=organization_id,
            business_id=business_id,
        )
        steps = list(current.completed_steps)
        if completed_step not in steps:
            steps.append(completed_step)

        return await self._repo.upsert_onboarding_progress(
            actor=actor,
            organization_id=organization_id,
            business_id=business_id,
            payload=OnboardingProgressUpdateRequest(
                current_step=next_step,
                completed_steps=steps,
                is_completed=current.is_completed,
            ),
        )

    async def get_onboarding_bundle(
        self, actor: AuthenticatedUser, organization_id: UUID
    ) -> OnboardingBundleResponse:
        """Load the complete Stage 2 onboarding state for a verified member."""
        await self._require_member(actor=actor, organization_id=organization_id)
        org = await self._repo.get_organization_detail(
            actor=actor, organization_id=organization_id
        )
        business_id = await self._repo.get_or_create_primary_business_id(
            actor=actor, organization_id=organization_id
        )

        profile = await self._repo.get_business_profile(
            actor=actor, organization_id=organization_id, business_id=business_id
        )
        hours = await self._repo.get_business_hours(
            actor=actor, organization_id=organization_id, business_id=business_id
        )
        languages = await self._repo.get_business_languages(
            actor=actor, organization_id=organization_id, business_id=business_id
        )
        assistant = await self._repo.get_assistant_settings(
            actor=actor, organization_id=organization_id, business_id=business_id
        )
        faqs = await self._repo.list_faqs(
            actor=actor, organization_id=organization_id, business_id=business_id
        )
        escalation = await self._repo.get_escalation_settings(
            actor=actor, organization_id=organization_id, business_id=business_id
        )
        progress = await self._repo.get_onboarding_progress(
            actor=actor, organization_id=organization_id, business_id=business_id
        )

        is_healthcare = org.industry in {
            OrganizationIndustry.CLINIC,
            OrganizationIndustry.HOSPITAL,
        }

        return OnboardingBundleResponse(
            organization=org,
            business_id=business_id,
            profile=profile,
            hours=hours,
            languages=languages,
            assistant=assistant,
            faqs=faqs,
            faq_templates=INDUSTRY_FAQ_TEMPLATES.get(org.industry, []),
            escalation=escalation,
            healthcare_safeguards=HealthcareSafeguardNotice(
                applies_to_healthcare=is_healthcare
            ),
            progress=progress,
        )

    async def update_industry(
        self,
        actor: AuthenticatedUser,
        organization_id: UUID,
        payload: UpdateIndustryRequest,
    ) -> OrganizationDetailResponse:
        """Confirm or update the organization's industry (Owner/Admin only)."""
        await self._require_owner_or_admin(actor=actor, organization_id=organization_id)
        business_id = await self._repo.get_or_create_primary_business_id(
            actor=actor, organization_id=organization_id
        )
        updated_org = await self._repo.update_organization_industry(
            actor=actor,
            organization_id=organization_id,
            industry=payload.industry,
        )
        await self._record_step_completed(
            actor=actor,
            organization_id=organization_id,
            business_id=business_id,
            completed_step=OnboardingStepId.INDUSTRY,
            next_step=OnboardingStepId.PROFILE,
        )
        return updated_org

    async def get_profile(
        self, actor: AuthenticatedUser, organization_id: UUID
    ) -> BusinessProfileResponse:
        await self._require_member(actor=actor, organization_id=organization_id)
        business_id = await self._repo.get_or_create_primary_business_id(
            actor=actor, organization_id=organization_id
        )
        return await self._repo.get_business_profile(
            actor=actor, organization_id=organization_id, business_id=business_id
        )

    async def update_profile(
        self,
        actor: AuthenticatedUser,
        organization_id: UUID,
        payload: BusinessProfileUpdateRequest,
    ) -> BusinessProfileResponse:
        await self._require_owner_or_admin(actor=actor, organization_id=organization_id)
        business_id = await self._repo.get_or_create_primary_business_id(
            actor=actor, organization_id=organization_id
        )
        profile = await self._repo.upsert_business_profile(
            actor=actor,
            organization_id=organization_id,
            business_id=business_id,
            payload=payload,
        )
        await self._record_step_completed(
            actor=actor,
            organization_id=organization_id,
            business_id=business_id,
            completed_step=OnboardingStepId.PROFILE,
            next_step=OnboardingStepId.HOURS,
        )
        return profile

    async def get_hours(
        self, actor: AuthenticatedUser, organization_id: UUID
    ) -> BusinessHoursResponse:
        await self._require_member(actor=actor, organization_id=organization_id)
        business_id = await self._repo.get_or_create_primary_business_id(
            actor=actor, organization_id=organization_id
        )
        return await self._repo.get_business_hours(
            actor=actor, organization_id=organization_id, business_id=business_id
        )

    async def update_hours(
        self,
        actor: AuthenticatedUser,
        organization_id: UUID,
        payload: BusinessHoursUpdateRequest,
    ) -> BusinessHoursResponse:
        await self._require_owner_or_admin(actor=actor, organization_id=organization_id)
        business_id = await self._repo.get_or_create_primary_business_id(
            actor=actor, organization_id=organization_id
        )
        hours = await self._repo.upsert_business_hours(
            actor=actor,
            organization_id=organization_id,
            business_id=business_id,
            payload=payload,
        )
        await self._record_step_completed(
            actor=actor,
            organization_id=organization_id,
            business_id=business_id,
            completed_step=OnboardingStepId.HOURS,
            next_step=OnboardingStepId.LANGUAGES,
        )
        return hours

    async def get_languages(
        self, actor: AuthenticatedUser, organization_id: UUID
    ) -> BusinessLanguagesResponse:
        await self._require_member(actor=actor, organization_id=organization_id)
        business_id = await self._repo.get_or_create_primary_business_id(
            actor=actor, organization_id=organization_id
        )
        return await self._repo.get_business_languages(
            actor=actor, organization_id=organization_id, business_id=business_id
        )

    async def update_languages(
        self,
        actor: AuthenticatedUser,
        organization_id: UUID,
        payload: BusinessLanguagesUpdateRequest,
    ) -> BusinessLanguagesResponse:
        await self._require_owner_or_admin(actor=actor, organization_id=organization_id)
        business_id = await self._repo.get_or_create_primary_business_id(
            actor=actor, organization_id=organization_id
        )
        langs = await self._repo.upsert_business_languages(
            actor=actor,
            organization_id=organization_id,
            business_id=business_id,
            payload=payload,
        )
        await self._record_step_completed(
            actor=actor,
            organization_id=organization_id,
            business_id=business_id,
            completed_step=OnboardingStepId.LANGUAGES,
            next_step=OnboardingStepId.ASSISTANT,
        )
        return langs

    async def get_assistant(
        self, actor: AuthenticatedUser, organization_id: UUID
    ) -> AssistantSettingsResponse:
        await self._require_member(actor=actor, organization_id=organization_id)
        business_id = await self._repo.get_or_create_primary_business_id(
            actor=actor, organization_id=organization_id
        )
        return await self._repo.get_assistant_settings(
            actor=actor, organization_id=organization_id, business_id=business_id
        )

    async def update_assistant(
        self,
        actor: AuthenticatedUser,
        organization_id: UUID,
        payload: AssistantSettingsUpdateRequest,
    ) -> AssistantSettingsResponse:
        await self._require_owner_or_admin(actor=actor, organization_id=organization_id)
        business_id = await self._repo.get_or_create_primary_business_id(
            actor=actor, organization_id=organization_id
        )
        assistant = await self._repo.upsert_assistant_settings(
            actor=actor,
            organization_id=organization_id,
            business_id=business_id,
            payload=payload,
        )
        await self._record_step_completed(
            actor=actor,
            organization_id=organization_id,
            business_id=business_id,
            completed_step=OnboardingStepId.ASSISTANT,
            next_step=OnboardingStepId.FAQS,
        )
        return assistant

    async def list_faqs(
        self, actor: AuthenticatedUser, organization_id: UUID
    ) -> List[BusinessFaqResponse]:
        await self._require_member(actor=actor, organization_id=organization_id)
        business_id = await self._repo.get_or_create_primary_business_id(
            actor=actor, organization_id=organization_id
        )
        return await self._repo.list_faqs(
            actor=actor, organization_id=organization_id, business_id=business_id
        )

    async def create_faq(
        self,
        actor: AuthenticatedUser,
        organization_id: UUID,
        payload: BusinessFaqCreateRequest,
    ) -> BusinessFaqResponse:
        await self._require_owner_or_admin(actor=actor, organization_id=organization_id)
        business_id = await self._repo.get_or_create_primary_business_id(
            actor=actor, organization_id=organization_id
        )
        faq = await self._repo.create_faq(
            actor=actor,
            organization_id=organization_id,
            business_id=business_id,
            payload=payload,
        )
        await self._record_step_completed(
            actor=actor,
            organization_id=organization_id,
            business_id=business_id,
            completed_step=OnboardingStepId.FAQS,
            next_step=OnboardingStepId.ESCALATION,
        )
        return faq

    async def update_faq(
        self,
        actor: AuthenticatedUser,
        organization_id: UUID,
        faq_id: UUID,
        payload: BusinessFaqUpdateRequest,
    ) -> BusinessFaqResponse:
        await self._require_owner_or_admin(actor=actor, organization_id=organization_id)
        business_id = await self._repo.get_or_create_primary_business_id(
            actor=actor, organization_id=organization_id
        )
        return await self._repo.update_faq(
            actor=actor,
            organization_id=organization_id,
            business_id=business_id,
            faq_id=faq_id,
            payload=payload,
        )

    async def delete_faq(
        self, actor: AuthenticatedUser, organization_id: UUID, faq_id: UUID
    ) -> None:
        await self._require_owner_or_admin(actor=actor, organization_id=organization_id)
        business_id = await self._repo.get_or_create_primary_business_id(
            actor=actor, organization_id=organization_id
        )
        await self._repo.delete_faq(
            actor=actor,
            organization_id=organization_id,
            business_id=business_id,
            faq_id=faq_id,
        )

    async def get_escalation(
        self, actor: AuthenticatedUser, organization_id: UUID
    ) -> EscalationSettingsResponse:
        await self._require_member(actor=actor, organization_id=organization_id)
        business_id = await self._repo.get_or_create_primary_business_id(
            actor=actor, organization_id=organization_id
        )
        return await self._repo.get_escalation_settings(
            actor=actor, organization_id=organization_id, business_id=business_id
        )

    async def update_escalation(
        self,
        actor: AuthenticatedUser,
        organization_id: UUID,
        payload: EscalationSettingsUpdateRequest,
    ) -> EscalationSettingsResponse:
        await self._require_owner_or_admin(actor=actor, organization_id=organization_id)
        business_id = await self._repo.get_or_create_primary_business_id(
            actor=actor, organization_id=organization_id
        )
        esc = await self._repo.upsert_escalation_settings(
            actor=actor,
            organization_id=organization_id,
            business_id=business_id,
            payload=payload,
        )
        await self._record_step_completed(
            actor=actor,
            organization_id=organization_id,
            business_id=business_id,
            completed_step=OnboardingStepId.ESCALATION,
            next_step=OnboardingStepId.REVIEW,
        )
        return esc

    async def get_progress(
        self, actor: AuthenticatedUser, organization_id: UUID
    ) -> OnboardingProgressResponse:
        await self._require_member(actor=actor, organization_id=organization_id)
        business_id = await self._repo.get_or_create_primary_business_id(
            actor=actor, organization_id=organization_id
        )
        return await self._repo.get_onboarding_progress(
            actor=actor, organization_id=organization_id, business_id=business_id
        )

    async def update_progress(
        self,
        actor: AuthenticatedUser,
        organization_id: UUID,
        payload: OnboardingProgressUpdateRequest,
    ) -> OnboardingProgressResponse:
        await self._require_owner_or_admin(actor=actor, organization_id=organization_id)
        business_id = await self._repo.get_or_create_primary_business_id(
            actor=actor, organization_id=organization_id
        )
        return await self._repo.upsert_onboarding_progress(
            actor=actor,
            organization_id=organization_id,
            business_id=business_id,
            payload=payload,
        )


def get_onboarding_service(
    repository: OnboardingRepositoryProtocol = Depends(get_onboarding_repository),
) -> OnboardingService:
    """FastAPI dependency returning an OnboardingService instance."""
    return OnboardingService(repository=repository)
