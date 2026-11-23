"""Repository layer for Stage 2 organization-scoped business onboarding.

Provides:
1. `InMemoryOnboardingRepository` — multi-tenant in-memory persistence coupled to
   `InMemoryOrganizationRepository` with zero hardcoded/fake organizations.
2. `SupabaseRestOnboardingRepository` — Supabase PostgREST persistence forwarding
   the caller's verified Bearer JWT so PostgreSQL RLS policies are enforced.
"""

from datetime import datetime, timezone
from typing import Dict, List, Optional, Protocol
from uuid import UUID, uuid4
import httpx
from fastapi import HTTPException, status
from app.core.auth import AuthenticatedUser
from app.core.config import Settings
from app.core.internal_voice import (
    INTERNAL_VOICE_ISSUER,
    verify_internal_voice_actor,
)
from app.modules.onboarding.schemas import (
    AssistantPersonality,
    AssistantResponseStyle,
    AssistantSettingsResponse,
    AssistantSettingsUpdateRequest,
    BusinessFaqCreateRequest,
    BusinessFaqResponse,
    BusinessFaqUpdateRequest,
    BusinessHoursResponse,
    BusinessHoursUpdateRequest,
    BusinessLanguageItemResponse,
    BusinessLanguagesResponse,
    BusinessLanguagesUpdateRequest,
    BusinessProfileResponse,
    BusinessProfileUpdateRequest,
    EscalationMethod,
    EscalationSettingsResponse,
    EscalationSettingsUpdateRequest,
    LanguageCode,
    OnboardingProgressResponse,
    OnboardingProgressUpdateRequest,
    OnboardingStepId,
    WeekdayHoursItem,
)
from app.modules.organizations.repository import InMemoryOrganizationRepository
from app.modules.organizations.schemas import (
    OrganizationDetailResponse,
    OrganizationIndustry,
    OrganizationRole,
)


def _default_weekly_schedule() -> List[WeekdayHoursItem]:
    """Return a clean default 7-day schedule (Mon-Sat 09:00-18:00, Sun closed)."""
    items: List[WeekdayHoursItem] = []
    for day in range(7):
        if day == 0:
            items.append(
                WeekdayHoursItem(
                    weekday=0,
                    is_closed=True,
                    opens_at=None,
                    closes_at=None,
                    is_overnight=False,
                )
            )
        else:
            items.append(
                WeekdayHoursItem(
                    weekday=day,
                    is_closed=False,
                    opens_at="09:00",
                    closes_at="18:00",
                    is_overnight=False,
                )
            )
    return items


class OnboardingRepositoryProtocol(Protocol):
    """Persistence contract for Stage 2 business onboarding."""

    async def get_member_role(
        self, actor: AuthenticatedUser, organization_id: UUID
    ) -> Optional[OrganizationRole]:
        ...

    async def get_organization_detail(
        self, actor: AuthenticatedUser, organization_id: UUID
    ) -> OrganizationDetailResponse:
        ...

    async def get_or_create_primary_business_id(
        self, actor: AuthenticatedUser, organization_id: UUID
    ) -> UUID:
        ...

    async def update_organization_industry(
        self,
        actor: AuthenticatedUser,
        organization_id: UUID,
        industry: OrganizationIndustry,
    ) -> OrganizationDetailResponse:
        ...

    async def get_business_profile(
        self, actor: AuthenticatedUser, organization_id: UUID, business_id: UUID
    ) -> BusinessProfileResponse:
        ...

    async def upsert_business_profile(
        self,
        actor: AuthenticatedUser,
        organization_id: UUID,
        business_id: UUID,
        payload: BusinessProfileUpdateRequest,
    ) -> BusinessProfileResponse:
        ...

    async def get_business_hours(
        self, actor: AuthenticatedUser, organization_id: UUID, business_id: UUID
    ) -> BusinessHoursResponse:
        ...

    async def upsert_business_hours(
        self,
        actor: AuthenticatedUser,
        organization_id: UUID,
        business_id: UUID,
        payload: BusinessHoursUpdateRequest,
    ) -> BusinessHoursResponse:
        ...

    async def get_business_languages(
        self, actor: AuthenticatedUser, organization_id: UUID, business_id: UUID
    ) -> BusinessLanguagesResponse:
        ...

    async def upsert_business_languages(
        self,
        actor: AuthenticatedUser,
        organization_id: UUID,
        business_id: UUID,
        payload: BusinessLanguagesUpdateRequest,
    ) -> BusinessLanguagesResponse:
        ...

    async def get_assistant_settings(
        self, actor: AuthenticatedUser, organization_id: UUID, business_id: UUID
    ) -> AssistantSettingsResponse:
        ...

    async def upsert_assistant_settings(
        self,
        actor: AuthenticatedUser,
        organization_id: UUID,
        business_id: UUID,
        payload: AssistantSettingsUpdateRequest,
    ) -> AssistantSettingsResponse:
        ...

    async def list_faqs(
        self, actor: AuthenticatedUser, organization_id: UUID, business_id: UUID
    ) -> List[BusinessFaqResponse]:
        ...

    async def create_faq(
        self,
        actor: AuthenticatedUser,
        organization_id: UUID,
        business_id: UUID,
        payload: BusinessFaqCreateRequest,
    ) -> BusinessFaqResponse:
        ...

    async def update_faq(
        self,
        actor: AuthenticatedUser,
        organization_id: UUID,
        business_id: UUID,
        faq_id: UUID,
        payload: BusinessFaqUpdateRequest,
    ) -> BusinessFaqResponse:
        ...

    async def delete_faq(
        self,
        actor: AuthenticatedUser,
        organization_id: UUID,
        business_id: UUID,
        faq_id: UUID,
    ) -> None:
        ...

    async def get_escalation_settings(
        self, actor: AuthenticatedUser, organization_id: UUID, business_id: UUID
    ) -> EscalationSettingsResponse:
        ...

    async def upsert_escalation_settings(
        self,
        actor: AuthenticatedUser,
        organization_id: UUID,
        business_id: UUID,
        payload: EscalationSettingsUpdateRequest,
    ) -> EscalationSettingsResponse:
        ...

    async def get_onboarding_progress(
        self, actor: AuthenticatedUser, organization_id: UUID, business_id: UUID
    ) -> OnboardingProgressResponse:
        ...

    async def upsert_onboarding_progress(
        self,
        actor: AuthenticatedUser,
        organization_id: UUID,
        business_id: UUID,
        payload: OnboardingProgressUpdateRequest,
    ) -> OnboardingProgressResponse:
        ...


class InMemoryOnboardingRepository:
    """Multi-tenant in-memory onboarding store backed by InMemoryOrganizationRepository."""

    def __init__(self, org_repo: InMemoryOrganizationRepository) -> None:
        self._org_repo = org_repo
        self._profiles: Dict[UUID, BusinessProfileResponse] = {}
        self._hours: Dict[UUID, BusinessHoursResponse] = {}
        self._languages: Dict[UUID, BusinessLanguagesResponse] = {}
        self._assistant: Dict[UUID, AssistantSettingsResponse] = {}
        self._faqs: Dict[UUID, List[BusinessFaqResponse]] = {}
        self._escalation: Dict[UUID, EscalationSettingsResponse] = {}
        self._progress: Dict[UUID, OnboardingProgressResponse] = {}

    async def get_member_role(
        self, actor: AuthenticatedUser, organization_id: UUID
    ) -> Optional[OrganizationRole]:
        return await self._org_repo.get_member_role(actor, organization_id, actor.id)

    async def get_organization_detail(
        self, actor: AuthenticatedUser, organization_id: UUID
    ) -> OrganizationDetailResponse:
        return await self._org_repo.get_organization_for_member(actor, organization_id)

    async def get_or_create_primary_business_id(
        self, actor: AuthenticatedUser, organization_id: UUID
    ) -> UUID:
        businesses = self._org_repo._businesses.get(organization_id, [])
        if businesses:
            return businesses[0]["id"]  # type: ignore[return-value]

        org = self._org_repo._organizations.get(organization_id)
        if not org:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied: organization not found.",
            )
        now = datetime.now(timezone.utc)
        business_id = uuid4()
        self._org_repo._businesses[organization_id] = [
            {
                "id": business_id,
                "organization_id": organization_id,
                "name": str(org["name"]),
                "timezone": "UTC",
                "created_at": now,
                "updated_at": now,
            }
        ]
        return business_id

    async def update_organization_industry(
        self,
        actor: AuthenticatedUser,
        organization_id: UUID,
        industry: OrganizationIndustry,
    ) -> OrganizationDetailResponse:
        org = self._org_repo._organizations.get(organization_id)
        if not org:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied: organization not found.",
            )
        org["industry"] = industry
        org["updated_at"] = datetime.now(timezone.utc)
        return await self.get_organization_detail(actor, organization_id)

    async def get_business_profile(
        self, actor: AuthenticatedUser, organization_id: UUID, business_id: UUID
    ) -> BusinessProfileResponse:
        existing = self._profiles.get(business_id)
        if existing is not None:
            return existing

        org = await self.get_organization_detail(actor, organization_id)
        businesses = self._org_repo._businesses.get(organization_id, [])
        tz = str(businesses[0].get("timezone", "UTC")) if businesses else "UTC"
        now = datetime.now(timezone.utc)

        default_profile = BusinessProfileResponse(
            id=uuid4(),
            organization_id=organization_id,
            business_id=business_id,
            display_name=org.name,
            description=None,
            phone=None,
            email=None,
            website=None,
            address=None,
            city=None,
            state=None,
            country=None,
            postal_code=None,
            timezone=tz,
            created_at=now,
            updated_at=now,
        )
        self._profiles[business_id] = default_profile
        return default_profile

    async def upsert_business_profile(
        self,
        actor: AuthenticatedUser,
        organization_id: UUID,
        business_id: UUID,
        payload: BusinessProfileUpdateRequest,
    ) -> BusinessProfileResponse:
        now = datetime.now(timezone.utc)
        existing = self._profiles.get(business_id)
        profile_id = existing.id if existing else uuid4()
        created_at = existing.created_at if existing else now

        updated = BusinessProfileResponse(
            id=profile_id,
            organization_id=organization_id,
            business_id=business_id,
            display_name=payload.display_name,
            description=payload.description,
            phone=payload.phone,
            email=payload.email,
            website=payload.website,
            address=payload.address,
            city=payload.city,
            state=payload.state,
            country=payload.country,
            postal_code=payload.postal_code,
            timezone=payload.timezone,
            created_at=created_at,
            updated_at=now,
        )
        self._profiles[business_id] = updated

        # Synchronize core business record
        businesses = self._org_repo._businesses.get(organization_id, [])
        if businesses:
            businesses[0]["name"] = payload.display_name
            businesses[0]["description"] = payload.description
            businesses[0]["phone"] = payload.phone
            businesses[0]["email"] = payload.email
            businesses[0]["address"] = payload.address
            businesses[0]["timezone"] = payload.timezone
            businesses[0]["updated_at"] = now

        if business_id in self._hours:
            self._hours[business_id].timezone = payload.timezone

        return updated

    async def get_business_hours(
        self, actor: AuthenticatedUser, organization_id: UUID, business_id: UUID
    ) -> BusinessHoursResponse:
        existing = self._hours.get(business_id)
        if existing is not None:
            return existing

        profile = await self.get_business_profile(actor, organization_id, business_id)
        default_hours = BusinessHoursResponse(
            organization_id=organization_id,
            business_id=business_id,
            timezone=profile.timezone,
            schedule=_default_weekly_schedule(),
        )
        self._hours[business_id] = default_hours
        return default_hours

    async def upsert_business_hours(
        self,
        actor: AuthenticatedUser,
        organization_id: UUID,
        business_id: UUID,
        payload: BusinessHoursUpdateRequest,
    ) -> BusinessHoursResponse:
        updated = BusinessHoursResponse(
            organization_id=organization_id,
            business_id=business_id,
            timezone=payload.timezone,
            schedule=payload.schedule,
        )
        self._hours[business_id] = updated

        if business_id in self._profiles:
            self._profiles[business_id].timezone = payload.timezone
            self._profiles[business_id].updated_at = datetime.now(timezone.utc)

        return updated

    async def get_business_languages(
        self, actor: AuthenticatedUser, organization_id: UUID, business_id: UUID
    ) -> BusinessLanguagesResponse:
        existing = self._languages.get(business_id)
        if existing is not None:
            return existing

        now = datetime.now(timezone.utc)
        default_lang = BusinessLanguagesResponse(
            organization_id=organization_id,
            business_id=business_id,
            primary_language=LanguageCode.ENGLISH,
            supported_languages=[LanguageCode.ENGLISH],
            entries=[
                BusinessLanguageItemResponse(
                    id=uuid4(),
                    organization_id=organization_id,
                    business_id=business_id,
                    language_code=LanguageCode.ENGLISH,
                    is_primary=True,
                    created_at=now,
                )
            ],
        )
        self._languages[business_id] = default_lang
        return default_lang

    async def upsert_business_languages(
        self,
        actor: AuthenticatedUser,
        organization_id: UUID,
        business_id: UUID,
        payload: BusinessLanguagesUpdateRequest,
    ) -> BusinessLanguagesResponse:
        now = datetime.now(timezone.utc)
        entries: List[BusinessLanguageItemResponse] = []
        for code in payload.supported_languages:
            entries.append(
                BusinessLanguageItemResponse(
                    id=uuid4(),
                    organization_id=organization_id,
                    business_id=business_id,
                    language_code=code,
                    is_primary=(code == payload.primary_language),
                    created_at=now,
                )
            )

        updated = BusinessLanguagesResponse(
            organization_id=organization_id,
            business_id=business_id,
            primary_language=payload.primary_language,
            supported_languages=payload.supported_languages,
            entries=entries,
        )
        self._languages[business_id] = updated
        return updated

    async def get_assistant_settings(
        self, actor: AuthenticatedUser, organization_id: UUID, business_id: UUID
    ) -> AssistantSettingsResponse:
        existing = self._assistant.get(business_id)
        if existing is not None:
            return existing

        org = await self.get_organization_detail(actor, organization_id)
        now = datetime.now(timezone.utc)
        default_assistant = AssistantSettingsResponse(
            id=uuid4(),
            organization_id=organization_id,
            business_id=business_id,
            assistant_name=f"{org.name} Receptionist",
            greeting=f"Hello! Thank you for calling {org.name}. How may I help you today?",
            personality=AssistantPersonality.PROFESSIONAL,
            response_style=AssistantResponseStyle.BALANCED,
            enabled=False,
            created_at=now,
            updated_at=now,
        )
        self._assistant[business_id] = default_assistant
        return default_assistant

    async def upsert_assistant_settings(
        self,
        actor: AuthenticatedUser,
        organization_id: UUID,
        business_id: UUID,
        payload: AssistantSettingsUpdateRequest,
    ) -> AssistantSettingsResponse:
        now = datetime.now(timezone.utc)
        existing = self._assistant.get(business_id)
        record_id = existing.id if existing else uuid4()
        created_at = existing.created_at if existing else now

        updated = AssistantSettingsResponse(
            id=record_id,
            organization_id=organization_id,
            business_id=business_id,
            assistant_name=payload.assistant_name,
            greeting=payload.greeting,
            personality=payload.personality,
            response_style=payload.response_style,
            enabled=payload.enabled,
            created_at=created_at,
            updated_at=now,
        )
        self._assistant[business_id] = updated
        return updated

    async def list_faqs(
        self, actor: AuthenticatedUser, organization_id: UUID, business_id: UUID
    ) -> List[BusinessFaqResponse]:
        items = self._faqs.get(business_id, [])
        return sorted(items, key=lambda x: (x.sort_order, x.created_at))

    async def create_faq(
        self,
        actor: AuthenticatedUser,
        organization_id: UUID,
        business_id: UUID,
        payload: BusinessFaqCreateRequest,
    ) -> BusinessFaqResponse:
        now = datetime.now(timezone.utc)
        faq = BusinessFaqResponse(
            id=uuid4(),
            organization_id=organization_id,
            business_id=business_id,
            question=payload.question,
            answer=payload.answer,
            category=payload.category,
            is_active=payload.is_active,
            sort_order=payload.sort_order,
            created_at=now,
            updated_at=now,
        )
        self._faqs.setdefault(business_id, []).append(faq)
        return faq

    async def update_faq(
        self,
        actor: AuthenticatedUser,
        organization_id: UUID,
        business_id: UUID,
        faq_id: UUID,
        payload: BusinessFaqUpdateRequest,
    ) -> BusinessFaqResponse:
        items = self._faqs.get(business_id, [])
        for idx, existing in enumerate(items):
            if existing.id == faq_id and existing.organization_id == organization_id:
                updated = BusinessFaqResponse(
                    id=existing.id,
                    organization_id=organization_id,
                    business_id=business_id,
                    question=(
                        payload.question.strip()
                        if payload.question is not None
                        else existing.question
                    ),
                    answer=(
                        payload.answer.strip()
                        if payload.answer is not None
                        else existing.answer
                    ),
                    category=(
                        payload.category.strip()
                        if payload.category is not None
                        else existing.category
                    ),
                    is_active=(
                        payload.is_active
                        if payload.is_active is not None
                        else existing.is_active
                    ),
                    sort_order=(
                        payload.sort_order
                        if payload.sort_order is not None
                        else existing.sort_order
                    ),
                    created_at=existing.created_at,
                    updated_at=datetime.now(timezone.utc),
                )
                items[idx] = updated
                return updated

        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="FAQ item not found in this organization.",
        )

    async def delete_faq(
        self,
        actor: AuthenticatedUser,
        organization_id: UUID,
        business_id: UUID,
        faq_id: UUID,
    ) -> None:
        items = self._faqs.get(business_id, [])
        for idx, existing in enumerate(items):
            if existing.id == faq_id and existing.organization_id == organization_id:
                items.pop(idx)
                return
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="FAQ item not found in this organization.",
        )

    async def get_escalation_settings(
        self, actor: AuthenticatedUser, organization_id: UUID, business_id: UUID
    ) -> EscalationSettingsResponse:
        existing = self._escalation.get(business_id)
        if existing is not None:
            return existing

        now = datetime.now(timezone.utc)
        default_esc = EscalationSettingsResponse(
            id=uuid4(),
            organization_id=organization_id,
            business_id=business_id,
            enabled=False,
            contact_name=None,
            contact_email=None,
            contact_phone=None,
            preferred_method=EscalationMethod.PHONE,
            escalation_instructions=None,
            created_at=now,
            updated_at=now,
        )
        self._escalation[business_id] = default_esc
        return default_esc

    async def upsert_escalation_settings(
        self,
        actor: AuthenticatedUser,
        organization_id: UUID,
        business_id: UUID,
        payload: EscalationSettingsUpdateRequest,
    ) -> EscalationSettingsResponse:
        now = datetime.now(timezone.utc)
        existing = self._escalation.get(business_id)
        record_id = existing.id if existing else uuid4()
        created_at = existing.created_at if existing else now

        updated = EscalationSettingsResponse(
            id=record_id,
            organization_id=organization_id,
            business_id=business_id,
            enabled=payload.enabled,
            contact_name=payload.contact_name,
            contact_email=payload.contact_email,
            contact_phone=payload.contact_phone,
            preferred_method=payload.preferred_method,
            escalation_instructions=payload.escalation_instructions,
            created_at=created_at,
            updated_at=now,
        )
        self._escalation[business_id] = updated
        return updated

    async def get_onboarding_progress(
        self, actor: AuthenticatedUser, organization_id: UUID, business_id: UUID
    ) -> OnboardingProgressResponse:
        existing = self._progress.get(business_id)
        if existing is not None:
            return existing

        now = datetime.now(timezone.utc)
        default_prog = OnboardingProgressResponse(
            id=uuid4(),
            organization_id=organization_id,
            business_id=business_id,
            current_step=OnboardingStepId.INDUSTRY,
            completed_steps=[],
            is_completed=False,
            completed_at=None,
            created_at=now,
            updated_at=now,
        )
        self._progress[business_id] = default_prog
        return default_prog

    async def upsert_onboarding_progress(
        self,
        actor: AuthenticatedUser,
        organization_id: UUID,
        business_id: UUID,
        payload: OnboardingProgressUpdateRequest,
    ) -> OnboardingProgressResponse:
        now = datetime.now(timezone.utc)
        existing = self._progress.get(business_id)
        record_id = existing.id if existing else uuid4()
        created_at = existing.created_at if existing else now
        completed_at = (
            now
            if payload.is_completed and (not existing or not existing.completed_at)
            else (existing.completed_at if existing and payload.is_completed else None)
        )

        updated = OnboardingProgressResponse(
            id=record_id,
            organization_id=organization_id,
            business_id=business_id,
            current_step=payload.current_step,
            completed_steps=payload.completed_steps,
            is_completed=payload.is_completed,
            completed_at=completed_at,
            created_at=created_at,
            updated_at=now,
        )
        self._progress[business_id] = updated
        return updated


class SupabaseRestOnboardingRepository:
    """Supabase PostgREST onboarding repository forwarding user JWTs so RLS applies."""

    def __init__(self, settings: Settings) -> None:
        self._base_url = (settings.supabase_url or "").rstrip("/")
        self._anon_key = settings.supabase_anon_key or ""
        self._service_role_key = (
            settings.supabase_service_role_key.strip()
            if settings.supabase_service_role_key
            else None
        )

    def _headers(
        self,
        actor: AuthenticatedUser,
        *,
        allow_internal_voice_read: bool = False,
        organization_id: Optional[UUID] = None,
        business_id: Optional[UUID] = None,
    ) -> Dict[str, str]:
        if actor.issuer == INTERNAL_VOICE_ISSUER:
            if not allow_internal_voice_read or organization_id is None or business_id is None:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Access denied: internal voice sessions are not permitted on this onboarding operation.",
                )
            verify_internal_voice_actor(
                actor,
                organization_id=organization_id,
                business_id=business_id,
            )
            if not self._service_role_key:
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail="Voice agent database persistence requires SUPABASE_SERVICE_ROLE_KEY on the server.",
                )
            return {
                "apikey": self._service_role_key,
                "Authorization": f"Bearer {self._service_role_key}",
                "Content-Type": "application/json",
                "Prefer": "return=representation",
            }
        if not actor.raw_token:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Authenticated user JWT is required for onboarding database access.",
            )
        return {
            "apikey": self._anon_key,
            "Authorization": f"Bearer {actor.raw_token}",
            "Content-Type": "application/json",
            "Prefer": "return=representation",
        }

    async def get_member_role(
        self, actor: AuthenticatedUser, organization_id: UUID
    ) -> Optional[OrganizationRole]:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(
                f"{self._base_url}/rest/v1/organization_members",
                headers=self._headers(actor),
                params={
                    "organization_id": f"eq.{organization_id}",
                    "user_id": f"eq.{actor.id}",
                    "select": "role",
                },
            )
            if resp.status_code >= 400:
                return None
            rows = resp.json()
            return OrganizationRole(rows[0]["role"]) if rows else None

    async def get_organization_detail(
        self, actor: AuthenticatedUser, organization_id: UUID
    ) -> OrganizationDetailResponse:
        role = await self.get_member_role(actor, organization_id)
        if role is None:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied: you are not a member of this organization.",
            )
        async with httpx.AsyncClient(timeout=10.0) as client:
            org_resp = await client.get(
                f"{self._base_url}/rest/v1/organizations",
                headers=self._headers(actor),
                params={"id": f"eq.{organization_id}", "select": "*"},
            )
            members_resp = await client.get(
                f"{self._base_url}/rest/v1/organization_members",
                headers=self._headers(actor),
                params={"organization_id": f"eq.{organization_id}", "select": "id"},
            )
        rows = org_resp.json() if org_resp.status_code < 400 else []
        if not rows:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied.")
        org = rows[0]
        count = len(members_resp.json()) if members_resp.status_code < 400 else 1
        return OrganizationDetailResponse(
            id=UUID(org["id"]),
            name=org["name"],
            slug=org["slug"],
            industry=OrganizationIndustry(org["industry"]),
            membership_role=role,
            member_count=count,
            created_at=datetime.fromisoformat(org["created_at"].replace("Z", "+00:00")),
            updated_at=datetime.fromisoformat(org["updated_at"].replace("Z", "+00:00")),
        )

    async def get_or_create_primary_business_id(
        self, actor: AuthenticatedUser, organization_id: UUID
    ) -> UUID:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(
                f"{self._base_url}/rest/v1/businesses",
                headers=self._headers(actor),
                params={
                    "organization_id": f"eq.{organization_id}",
                    "select": "id",
                    "order": "created_at.asc",
                    "limit": "1",
                },
            )
            rows = resp.json() if resp.status_code < 400 else []
            if rows:
                return UUID(rows[0]["id"])

            org = await self.get_organization_detail(actor, organization_id)
            new_id = uuid4()
            await client.post(
                f"{self._base_url}/rest/v1/businesses",
                headers=self._headers(actor),
                json={
                    "id": str(new_id),
                    "organization_id": str(organization_id),
                    "name": org.name,
                    "timezone": "UTC",
                },
            )
            return new_id

    async def update_organization_industry(
        self,
        actor: AuthenticatedUser,
        organization_id: UUID,
        industry: OrganizationIndustry,
    ) -> OrganizationDetailResponse:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.patch(
                f"{self._base_url}/rest/v1/organizations",
                headers=self._headers(actor),
                params={"id": f"eq.{organization_id}"},
                json={"industry": industry.value},
            )
            if resp.status_code >= 400:
                raise HTTPException(
                    status_code=status.HTTP_502_BAD_GATEWAY,
                    detail="Failed to update organization industry.",
                )
        return await self.get_organization_detail(actor, organization_id)

    async def get_business_profile(
        self, actor: AuthenticatedUser, organization_id: UUID, business_id: UUID
    ) -> BusinessProfileResponse:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(
                f"{self._base_url}/rest/v1/business_profiles",
                headers=self._headers(
                    actor,
                    allow_internal_voice_read=True,
                    organization_id=organization_id,
                    business_id=business_id,
                ),
                params={
                    "organization_id": f"eq.{organization_id}",
                    "business_id": f"eq.{business_id}",
                    "select": "*",
                },
            )
            rows = resp.json() if resp.status_code < 400 else []
            if rows:
                r = rows[0]
                return BusinessProfileResponse(
                    id=UUID(r["id"]),
                    organization_id=UUID(r["organization_id"]),
                    business_id=UUID(r["business_id"]),
                    display_name=r["display_name"],
                    description=r.get("description"),
                    phone=r.get("phone"),
                    email=r.get("email"),
                    website=r.get("website"),
                    address=r.get("address"),
                    city=r.get("city"),
                    state=r.get("state"),
                    country=r.get("country"),
                    postal_code=r.get("postal_code"),
                    timezone=r.get("timezone", "UTC"),
                    created_at=datetime.fromisoformat(r["created_at"].replace("Z", "+00:00")),
                    updated_at=datetime.fromisoformat(r["updated_at"].replace("Z", "+00:00")),
                )
        org = await self.get_organization_detail(actor, organization_id)
        now = datetime.now(timezone.utc)
        return BusinessProfileResponse(
            id=uuid4(),
            organization_id=organization_id,
            business_id=business_id,
            display_name=org.name,
            timezone="UTC",
            created_at=now,
            updated_at=now,
        )

    async def upsert_business_profile(
        self,
        actor: AuthenticatedUser,
        organization_id: UUID,
        business_id: UUID,
        payload: BusinessProfileUpdateRequest,
    ) -> BusinessProfileResponse:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(
                f"{self._base_url}/rest/v1/business_profiles",
                headers={
                    **self._headers(actor),
                    "Prefer": "resolution=merge-duplicates,return=representation",
                },
                params={"on_conflict": "business_id"},
                json={
                    "organization_id": str(organization_id),
                    "business_id": str(business_id),
                    **payload.model_dump(),
                },
            )
            if resp.status_code >= 400:
                raise HTTPException(
                    status_code=status.HTTP_502_BAD_GATEWAY,
                    detail="Failed to save business profile.",
                )
            r = resp.json()[0]
            return BusinessProfileResponse(
                id=UUID(r["id"]),
                organization_id=UUID(r["organization_id"]),
                business_id=UUID(r["business_id"]),
                display_name=r["display_name"],
                description=r.get("description"),
                phone=r.get("phone"),
                email=r.get("email"),
                website=r.get("website"),
                address=r.get("address"),
                city=r.get("city"),
                state=r.get("state"),
                country=r.get("country"),
                postal_code=r.get("postal_code"),
                timezone=r.get("timezone", "UTC"),
                created_at=datetime.fromisoformat(r["created_at"].replace("Z", "+00:00")),
                updated_at=datetime.fromisoformat(r["updated_at"].replace("Z", "+00:00")),
            )

    async def get_business_hours(
        self, actor: AuthenticatedUser, organization_id: UUID, business_id: UUID
    ) -> BusinessHoursResponse:
        profile = await self.get_business_profile(actor, organization_id, business_id)
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(
                f"{self._base_url}/rest/v1/business_hours",
                headers=self._headers(
                    actor,
                    allow_internal_voice_read=True,
                    organization_id=organization_id,
                    business_id=business_id,
                ),
                params={
                    "organization_id": f"eq.{organization_id}",
                    "business_id": f"eq.{business_id}",
                    "select": "*",
                    "order": "weekday.asc",
                },
            )
            rows = resp.json() if resp.status_code < 400 else []
            if len(rows) == 7:
                schedule = [
                    WeekdayHoursItem(
                        weekday=int(r["weekday"]),
                        is_closed=bool(r["is_closed"]),
                        opens_at=str(r["opens_at"])[:5] if r.get("opens_at") else None,
                        closes_at=str(r["closes_at"])[:5] if r.get("closes_at") else None,
                        is_overnight=bool(r.get("is_overnight", False)),
                    )
                    for r in rows
                ]
                return BusinessHoursResponse(
                    organization_id=organization_id,
                    business_id=business_id,
                    timezone=profile.timezone,
                    schedule=schedule,
                )
        return BusinessHoursResponse(
            organization_id=organization_id,
            business_id=business_id,
            timezone=profile.timezone,
            schedule=_default_weekly_schedule(),
        )

    async def upsert_business_hours(
        self,
        actor: AuthenticatedUser,
        organization_id: UUID,
        business_id: UUID,
        payload: BusinessHoursUpdateRequest,
    ) -> BusinessHoursResponse:
        records = [
            {
                "organization_id": str(organization_id),
                "business_id": str(business_id),
                "weekday": item.weekday,
                "is_closed": item.is_closed,
                "opens_at": item.opens_at,
                "closes_at": item.closes_at,
                "is_overnight": item.is_overnight,
            }
            for item in payload.schedule
        ]
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(
                f"{self._base_url}/rest/v1/business_hours",
                headers={
                    **self._headers(actor),
                    "Prefer": "resolution=merge-duplicates,return=representation",
                },
                params={"on_conflict": "business_id,weekday"},
                json=records,
            )
            if resp.status_code >= 400:
                raise HTTPException(
                    status_code=status.HTTP_502_BAD_GATEWAY,
                    detail="Failed to save business hours.",
                )
        return BusinessHoursResponse(
            organization_id=organization_id,
            business_id=business_id,
            timezone=payload.timezone,
            schedule=payload.schedule,
        )

    async def get_business_languages(
        self, actor: AuthenticatedUser, organization_id: UUID, business_id: UUID
    ) -> BusinessLanguagesResponse:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(
                f"{self._base_url}/rest/v1/business_languages",
                headers=self._headers(actor),
                params={"business_id": f"eq.{business_id}", "select": "*"},
            )
            rows = resp.json() if resp.status_code < 400 else []
            if rows:
                entries = [
                    BusinessLanguageItemResponse(
                        id=UUID(r["id"]),
                        organization_id=UUID(r["organization_id"]),
                        business_id=UUID(r["business_id"]),
                        language_code=LanguageCode(r["language_code"]),
                        is_primary=bool(r["is_primary"]),
                        created_at=datetime.fromisoformat(r["created_at"].replace("Z", "+00:00")),
                    )
                    for r in rows
                ]
                primary = next(
                    (e.language_code for e in entries if e.is_primary),
                    entries[0].language_code,
                )
                return BusinessLanguagesResponse(
                    organization_id=organization_id,
                    business_id=business_id,
                    primary_language=primary,
                    supported_languages=[e.language_code for e in entries],
                    entries=entries,
                )
        now = datetime.now(timezone.utc)
        return BusinessLanguagesResponse(
            organization_id=organization_id,
            business_id=business_id,
            primary_language=LanguageCode.ENGLISH,
            supported_languages=[LanguageCode.ENGLISH],
            entries=[
                BusinessLanguageItemResponse(
                    id=uuid4(),
                    organization_id=organization_id,
                    business_id=business_id,
                    language_code=LanguageCode.ENGLISH,
                    is_primary=True,
                    created_at=now,
                )
            ],
        )

    async def upsert_business_languages(
        self,
        actor: AuthenticatedUser,
        organization_id: UUID,
        business_id: UUID,
        payload: BusinessLanguagesUpdateRequest,
    ) -> BusinessLanguagesResponse:
        async with httpx.AsyncClient(timeout=10.0) as client:
            await client.delete(
                f"{self._base_url}/rest/v1/business_languages",
                headers=self._headers(actor),
                params={"business_id": f"eq.{business_id}"},
            )
            records = [
                {
                    "organization_id": str(organization_id),
                    "business_id": str(business_id),
                    "language_code": code.value,
                    "is_primary": code == payload.primary_language,
                }
                for code in payload.supported_languages
            ]
            resp = await client.post(
                f"{self._base_url}/rest/v1/business_languages",
                headers=self._headers(actor),
                json=records,
            )
            if resp.status_code >= 400:
                raise HTTPException(
                    status_code=status.HTTP_502_BAD_GATEWAY,
                    detail="Failed to save business languages.",
                )
        return await self.get_business_languages(actor, organization_id, business_id)

    async def get_assistant_settings(
        self, actor: AuthenticatedUser, organization_id: UUID, business_id: UUID
    ) -> AssistantSettingsResponse:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(
                f"{self._base_url}/rest/v1/assistant_settings",
                headers=self._headers(actor),
                params={"business_id": f"eq.{business_id}", "select": "*"},
            )
            rows = resp.json() if resp.status_code < 400 else []
            if rows:
                r = rows[0]
                return AssistantSettingsResponse(
                    id=UUID(r["id"]),
                    organization_id=UUID(r["organization_id"]),
                    business_id=UUID(r["business_id"]),
                    assistant_name=r["assistant_name"],
                    greeting=r["greeting"],
                    personality=AssistantPersonality(r["personality"]),
                    response_style=AssistantResponseStyle(r["response_style"]),
                    enabled=bool(r["enabled"]),
                    created_at=datetime.fromisoformat(r["created_at"].replace("Z", "+00:00")),
                    updated_at=datetime.fromisoformat(r["updated_at"].replace("Z", "+00:00")),
                )
        org = await self.get_organization_detail(actor, organization_id)
        now = datetime.now(timezone.utc)
        return AssistantSettingsResponse(
            id=uuid4(),
            organization_id=organization_id,
            business_id=business_id,
            assistant_name=f"{org.name} Receptionist",
            greeting=f"Hello! Thank you for calling {org.name}. How may I help you today?",
            personality=AssistantPersonality.PROFESSIONAL,
            response_style=AssistantResponseStyle.BALANCED,
            enabled=False,
            created_at=now,
            updated_at=now,
        )

    async def upsert_assistant_settings(
        self,
        actor: AuthenticatedUser,
        organization_id: UUID,
        business_id: UUID,
        payload: AssistantSettingsUpdateRequest,
    ) -> AssistantSettingsResponse:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(
                f"{self._base_url}/rest/v1/assistant_settings",
                headers={
                    **self._headers(actor),
                    "Prefer": "resolution=merge-duplicates,return=representation",
                },
                params={"on_conflict": "business_id"},
                json={
                    "organization_id": str(organization_id),
                    "business_id": str(business_id),
                    "assistant_name": payload.assistant_name,
                    "greeting": payload.greeting,
                    "personality": payload.personality.value,
                    "response_style": payload.response_style.value,
                    "enabled": payload.enabled,
                },
            )
            if resp.status_code >= 400:
                raise HTTPException(
                    status_code=status.HTTP_502_BAD_GATEWAY,
                    detail="Failed to save assistant settings.",
                )
            r = resp.json()[0]
            return AssistantSettingsResponse(
                id=UUID(r["id"]),
                organization_id=UUID(r["organization_id"]),
                business_id=UUID(r["business_id"]),
                assistant_name=r["assistant_name"],
                greeting=r["greeting"],
                personality=AssistantPersonality(r["personality"]),
                response_style=AssistantResponseStyle(r["response_style"]),
                enabled=bool(r["enabled"]),
                created_at=datetime.fromisoformat(r["created_at"].replace("Z", "+00:00")),
                updated_at=datetime.fromisoformat(r["updated_at"].replace("Z", "+00:00")),
            )

    async def list_faqs(
        self, actor: AuthenticatedUser, organization_id: UUID, business_id: UUID
    ) -> List[BusinessFaqResponse]:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(
                f"{self._base_url}/rest/v1/business_faqs",
                headers=self._headers(actor),
                params={
                    "business_id": f"eq.{business_id}",
                    "select": "*",
                    "order": "sort_order.asc,created_at.asc",
                },
            )
            rows = resp.json() if resp.status_code < 400 else []
            return [
                BusinessFaqResponse(
                    id=UUID(r["id"]),
                    organization_id=UUID(r["organization_id"]),
                    business_id=UUID(r["business_id"]),
                    question=r["question"],
                    answer=r["answer"],
                    category=r["category"],
                    is_active=bool(r["is_active"]),
                    sort_order=int(r["sort_order"]),
                    created_at=datetime.fromisoformat(r["created_at"].replace("Z", "+00:00")),
                    updated_at=datetime.fromisoformat(r["updated_at"].replace("Z", "+00:00")),
                )
                for r in rows
            ]

    async def create_faq(
        self,
        actor: AuthenticatedUser,
        organization_id: UUID,
        business_id: UUID,
        payload: BusinessFaqCreateRequest,
    ) -> BusinessFaqResponse:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(
                f"{self._base_url}/rest/v1/business_faqs",
                headers=self._headers(actor),
                json={
                    "organization_id": str(organization_id),
                    "business_id": str(business_id),
                    **payload.model_dump(),
                },
            )
            if resp.status_code >= 400:
                raise HTTPException(
                    status_code=status.HTTP_502_BAD_GATEWAY,
                    detail="Failed to create FAQ.",
                )
            r = resp.json()[0]
            return BusinessFaqResponse(
                id=UUID(r["id"]),
                organization_id=UUID(r["organization_id"]),
                business_id=UUID(r["business_id"]),
                question=r["question"],
                answer=r["answer"],
                category=r["category"],
                is_active=bool(r["is_active"]),
                sort_order=int(r["sort_order"]),
                created_at=datetime.fromisoformat(r["created_at"].replace("Z", "+00:00")),
                updated_at=datetime.fromisoformat(r["updated_at"].replace("Z", "+00:00")),
            )

    async def update_faq(
        self,
        actor: AuthenticatedUser,
        organization_id: UUID,
        business_id: UUID,
        faq_id: UUID,
        payload: BusinessFaqUpdateRequest,
    ) -> BusinessFaqResponse:
        patch_data = {k: v for k, v in payload.model_dump().items() if v is not None}
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.patch(
                f"{self._base_url}/rest/v1/business_faqs",
                headers=self._headers(actor),
                params={
                    "id": f"eq.{faq_id}",
                    "organization_id": f"eq.{organization_id}",
                },
                json=patch_data,
            )
            rows = resp.json() if resp.status_code < 400 else []
            if not rows:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="FAQ item not found in this organization.",
                )
            r = rows[0]
            return BusinessFaqResponse(
                id=UUID(r["id"]),
                organization_id=UUID(r["organization_id"]),
                business_id=UUID(r["business_id"]),
                question=r["question"],
                answer=r["answer"],
                category=r["category"],
                is_active=bool(r["is_active"]),
                sort_order=int(r["sort_order"]),
                created_at=datetime.fromisoformat(r["created_at"].replace("Z", "+00:00")),
                updated_at=datetime.fromisoformat(r["updated_at"].replace("Z", "+00:00")),
            )

    async def delete_faq(
        self,
        actor: AuthenticatedUser,
        organization_id: UUID,
        business_id: UUID,
        faq_id: UUID,
    ) -> None:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.delete(
                f"{self._base_url}/rest/v1/business_faqs",
                headers=self._headers(actor),
                params={
                    "id": f"eq.{faq_id}",
                    "organization_id": f"eq.{organization_id}",
                },
            )
            rows = resp.json() if resp.status_code < 400 else []
            if not rows:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="FAQ item not found in this organization.",
                )

    async def get_escalation_settings(
        self, actor: AuthenticatedUser, organization_id: UUID, business_id: UUID
    ) -> EscalationSettingsResponse:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(
                f"{self._base_url}/rest/v1/escalation_settings",
                headers=self._headers(actor),
                params={"business_id": f"eq.{business_id}", "select": "*"},
            )
            rows = resp.json() if resp.status_code < 400 else []
            if rows:
                r = rows[0]
                return EscalationSettingsResponse(
                    id=UUID(r["id"]),
                    organization_id=UUID(r["organization_id"]),
                    business_id=UUID(r["business_id"]),
                    enabled=bool(r["enabled"]),
                    contact_name=r.get("contact_name"),
                    contact_email=r.get("contact_email"),
                    contact_phone=r.get("contact_phone"),
                    preferred_method=EscalationMethod(r["preferred_method"]),
                    escalation_instructions=r.get("escalation_instructions"),
                    created_at=datetime.fromisoformat(r["created_at"].replace("Z", "+00:00")),
                    updated_at=datetime.fromisoformat(r["updated_at"].replace("Z", "+00:00")),
                )
        now = datetime.now(timezone.utc)
        return EscalationSettingsResponse(
            id=uuid4(),
            organization_id=organization_id,
            business_id=business_id,
            enabled=False,
            preferred_method=EscalationMethod.PHONE,
            created_at=now,
            updated_at=now,
        )

    async def upsert_escalation_settings(
        self,
        actor: AuthenticatedUser,
        organization_id: UUID,
        business_id: UUID,
        payload: EscalationSettingsUpdateRequest,
    ) -> EscalationSettingsResponse:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(
                f"{self._base_url}/rest/v1/escalation_settings",
                headers={
                    **self._headers(actor),
                    "Prefer": "resolution=merge-duplicates,return=representation",
                },
                params={"on_conflict": "business_id"},
                json={
                    "organization_id": str(organization_id),
                    "business_id": str(business_id),
                    "enabled": payload.enabled,
                    "contact_name": payload.contact_name,
                    "contact_email": payload.contact_email,
                    "contact_phone": payload.contact_phone,
                    "preferred_method": payload.preferred_method.value,
                    "escalation_instructions": payload.escalation_instructions,
                },
            )
            if resp.status_code >= 400:
                raise HTTPException(
                    status_code=status.HTTP_502_BAD_GATEWAY,
                    detail="Failed to save escalation settings.",
                )
            r = resp.json()[0]
            return EscalationSettingsResponse(
                id=UUID(r["id"]),
                organization_id=UUID(r["organization_id"]),
                business_id=UUID(r["business_id"]),
                enabled=bool(r["enabled"]),
                contact_name=r.get("contact_name"),
                contact_email=r.get("contact_email"),
                contact_phone=r.get("contact_phone"),
                preferred_method=EscalationMethod(r["preferred_method"]),
                escalation_instructions=r.get("escalation_instructions"),
                created_at=datetime.fromisoformat(r["created_at"].replace("Z", "+00:00")),
                updated_at=datetime.fromisoformat(r["updated_at"].replace("Z", "+00:00")),
            )

    async def get_onboarding_progress(
        self, actor: AuthenticatedUser, organization_id: UUID, business_id: UUID
    ) -> OnboardingProgressResponse:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(
                f"{self._base_url}/rest/v1/onboarding_progress",
                headers=self._headers(actor),
                params={"business_id": f"eq.{business_id}", "select": "*"},
            )
            rows = resp.json() if resp.status_code < 400 else []
            if rows:
                r = rows[0]
                return OnboardingProgressResponse(
                    id=UUID(r["id"]),
                    organization_id=UUID(r["organization_id"]),
                    business_id=UUID(r["business_id"]),
                    current_step=OnboardingStepId(r["current_step"]),
                    completed_steps=[OnboardingStepId(s) for s in r.get("completed_steps", [])],
                    is_completed=bool(r["is_completed"]),
                    completed_at=(
                        datetime.fromisoformat(r["completed_at"].replace("Z", "+00:00"))
                        if r.get("completed_at")
                        else None
                    ),
                    created_at=datetime.fromisoformat(r["created_at"].replace("Z", "+00:00")),
                    updated_at=datetime.fromisoformat(r["updated_at"].replace("Z", "+00:00")),
                )
        now = datetime.now(timezone.utc)
        return OnboardingProgressResponse(
            id=uuid4(),
            organization_id=organization_id,
            business_id=business_id,
            current_step=OnboardingStepId.INDUSTRY,
            completed_steps=[],
            is_completed=False,
            completed_at=None,
            created_at=now,
            updated_at=now,
        )

    async def upsert_onboarding_progress(
        self,
        actor: AuthenticatedUser,
        organization_id: UUID,
        business_id: UUID,
        payload: OnboardingProgressUpdateRequest,
    ) -> OnboardingProgressResponse:
        now = datetime.now(timezone.utc)
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(
                f"{self._base_url}/rest/v1/onboarding_progress",
                headers={
                    **self._headers(actor),
                    "Prefer": "resolution=merge-duplicates,return=representation",
                },
                params={"on_conflict": "business_id"},
                json={
                    "organization_id": str(organization_id),
                    "business_id": str(business_id),
                    "current_step": payload.current_step.value,
                    "completed_steps": [s.value for s in payload.completed_steps],
                    "is_completed": payload.is_completed,
                    "completed_at": now.isoformat() if payload.is_completed else None,
                },
            )
            if resp.status_code >= 400:
                raise HTTPException(
                    status_code=status.HTTP_502_BAD_GATEWAY,
                    detail="Failed to save onboarding progress.",
                )
            r = resp.json()[0]
            return OnboardingProgressResponse(
                id=UUID(r["id"]),
                organization_id=UUID(r["organization_id"]),
                business_id=UUID(r["business_id"]),
                current_step=OnboardingStepId(r["current_step"]),
                completed_steps=[OnboardingStepId(s) for s in r.get("completed_steps", [])],
                is_completed=bool(r["is_completed"]),
                completed_at=(
                    datetime.fromisoformat(r["completed_at"].replace("Z", "+00:00"))
                    if r.get("completed_at")
                    else None
                ),
                created_at=datetime.fromisoformat(r["created_at"].replace("Z", "+00:00")),
                updated_at=datetime.fromisoformat(r["updated_at"].replace("Z", "+00:00")),
            )
