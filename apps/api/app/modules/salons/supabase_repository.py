"""Production Supabase PostgreSQL Repository for Stage 5 Salon Workflow Module.

Implements `SalonRepositoryProtocol` against Supabase PostgREST (`/rest/v1/*`):
- Forwards authenticated user Bearer JWTs so PostgreSQL Row Level Security (RLS)
  is enforced on every read and write.
- For verified internal voice agent sessions (`https://svario.internal/auth/v1`),
  uses `SUPABASE_SERVICE_ROLE_KEY` strictly scoped by backend-resolved
  `(organization_id, business_id)` filters, and fails closed (`503`) if unconfigured.
- Relies on PostgreSQL `excl_salon_appointments_no_staff_overlap` (`23P01`) for
  atomic double-booking protection and `uq_salon_appointments_business_idempotency`
  (`23505`) for idempotent booking replay.
"""

from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Any, Dict, List, Optional
from uuid import UUID
import httpx
from fastapi import HTTPException, status
from app.core.auth import AuthenticatedUser
from app.core.config import Settings
from app.core.internal_voice import (
    INTERNAL_VOICE_ISSUER,
    verify_internal_voice_actor,
)
from app.modules.organizations.schemas import OrganizationIndustry
from app.modules.salons.repository import _default_staff_working_hours
from app.modules.salons.schemas import (
    SalonAppointmentResponse,
    SalonAppointmentSource,
    SalonAppointmentStatus,
    SalonHolidayCreateRequest,
    SalonHolidayResponse,
    SalonServiceCreateRequest,
    SalonServiceResponse,
    SalonServiceUpdateRequest,
    SalonStaffBreakCreateRequest,
    SalonStaffBreakResponse,
    SalonStaffCreateRequest,
    SalonStaffResponse,
    SalonStaffUpdateRequest,
    SalonStaffWorkingHoursItem,
    SalonStaffWorkingHoursUpdateRequest,
    normalize_time_string,
)

MAX_PAGE_LIMIT = 500
DEFAULT_PAGE_LIMIT = 200


def _clamp_pagination(limit: int, offset: int) -> tuple[int, int]:
    bounded_limit = max(1, min(int(limit), MAX_PAGE_LIMIT))
    bounded_offset = max(0, int(offset))
    return bounded_limit, bounded_offset


def _parse_dt(raw: Optional[str]) -> Optional[datetime]:
    if not raw:
        return None
    return datetime.fromisoformat(raw.replace("Z", "+00:00"))


def _parse_date(raw: Optional[str]) -> Optional[date]:
    if not raw:
        return None
    return date.fromisoformat(raw[:10])


class SupabaseRestSalonRepository:
    """Supabase PostgREST implementation of `SalonRepositoryProtocol`."""

    _STAFF_SELECT = (
        "*,salon_staff_services(service_id,salon_services(name)),"
        "salon_staff_working_hours(weekday,is_off,start_time,end_time),"
        "salon_staff_breaks(id,organization_id,business_id,staff_id,weekday,specific_date,label,start_time,end_time,created_at)"
    )

    _APPT_SELECT = (
        "*,salon_services(name,duration_minutes,price,currency),"
        "salon_staff(full_name,role_designation)"
    )

    def __init__(self, settings: Settings) -> None:
        if (
            not settings.is_live_supabase_configured
            or not settings.supabase_url
            or not settings.supabase_anon_key
        ):
            raise RuntimeError(
                "SupabaseRestSalonRepository requires SUPABASE_URL and SUPABASE_ANON_KEY."
            )
        self._settings = settings
        self._base_url = settings.supabase_url.strip().rstrip("/")
        self._anon_key = settings.supabase_anon_key.strip()
        self._service_role_key = (
            settings.supabase_service_role_key.strip()
            if settings.supabase_service_role_key
            else None
        )

    def _headers(
        self,
        actor: AuthenticatedUser,
        organization_id: UUID,
        business_id: UUID,
        *,
        prefer: str = "return=representation",
    ) -> Dict[str, str]:
        if actor.issuer == INTERNAL_VOICE_ISSUER:
            verify_internal_voice_actor(
                actor,
                organization_id=organization_id,
                business_id=business_id,
                expected_industry=OrganizationIndustry.SALON,
            )
            if not self._service_role_key:
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail="Voice agent database persistence requires SUPABASE_SERVICE_ROLE_KEY on the server.",
                )
            token = self._service_role_key
            apikey = self._service_role_key
        else:
            if not actor.raw_token:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Authenticated user JWT is required for salon database access.",
                )
            token = actor.raw_token
            apikey = self._anon_key

        return {
            "apikey": apikey,
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "Prefer": prefer,
        }

    @staticmethod
    def _handle_error(resp: httpx.Response, *, context: str) -> None:
        if resp.status_code < 400:
            return
        try:
            body = resp.json()
        except Exception:
            body = {}
        pg_code = str(body.get("code") or "")
        msg = str(body.get("message") or "")

        if pg_code == "23P01" or "excl_salon_appointments_no_staff_overlap" in msg:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Appointment collision: Staff member is already booked during this time window.",
            )
        if pg_code == "23505" or resp.status_code == 409:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Resource conflict during {context}.",
            )
        if pg_code in {"22P02", "23503", "23514"} or resp.status_code == 400:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid salon data or reference during {context}.",
            )
        if resp.status_code in {401, 403}:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied by tenant database policy.",
            )
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Salon database error during {context}.",
        )

    # =========================================================================
    # Services CRUD
    # =========================================================================

    @staticmethod
    def _to_service(row: Dict[str, Any]) -> SalonServiceResponse:
        return SalonServiceResponse(
            id=UUID(row["id"]),
            organization_id=UUID(row["organization_id"]),
            business_id=UUID(row["business_id"]),
            name=row["name"],
            description=row.get("description"),
            category=row["category"],
            price=float(row["price"]),
            currency=row["currency"],
            duration_minutes=int(row["duration_minutes"]),
            is_active=bool(row["is_active"]),
            created_at=_parse_dt(row["created_at"]),  # type: ignore[arg-type]
            updated_at=_parse_dt(row["updated_at"]),  # type: ignore[arg-type]
        )

    async def create_service(
        self,
        actor: AuthenticatedUser,
        organization_id: UUID,
        business_id: UUID,
        payload: SalonServiceCreateRequest,
    ) -> SalonServiceResponse:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(
                f"{self._base_url}/rest/v1/salon_services",
                headers=self._headers(actor, organization_id, business_id),
                json={
                    "organization_id": str(organization_id),
                    "business_id": str(business_id),
                    "name": payload.name,
                    "description": payload.description,
                    "category": payload.category,
                    "price": payload.price,
                    "currency": payload.currency,
                    "duration_minutes": payload.duration_minutes,
                    "is_active": payload.is_active,
                },
            )
            self._handle_error(resp, context="create_service")
            return self._to_service(resp.json()[0])

    async def get_service(
        self,
        actor: AuthenticatedUser,
        organization_id: UUID,
        business_id: UUID,
        service_id: UUID,
    ) -> SalonServiceResponse:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(
                f"{self._base_url}/rest/v1/salon_services",
                headers=self._headers(actor, organization_id, business_id),
                params={
                    "id": f"eq.{service_id}",
                    "organization_id": f"eq.{organization_id}",
                    "business_id": f"eq.{business_id}",
                },
            )
            self._handle_error(resp, context="get_service")
            rows = resp.json()
            if not rows:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Salon service '{service_id}' was not found.",
                )
            return self._to_service(rows[0])

    async def list_services(
        self,
        actor: AuthenticatedUser,
        organization_id: UUID,
        business_id: UUID,
        category: Optional[str] = None,
        is_active: Optional[bool] = None,
        limit: int = DEFAULT_PAGE_LIMIT,
        offset: int = 0,
    ) -> List[SalonServiceResponse]:
        bounded_limit, bounded_offset = _clamp_pagination(limit, offset)
        params: Dict[str, str] = {
            "organization_id": f"eq.{organization_id}",
            "business_id": f"eq.{business_id}",
            "order": "category.asc,name.asc",
            "limit": str(bounded_limit),
            "offset": str(bounded_offset),
        }
        if category is not None:
            params["category"] = f"ilike.{category.strip()}"
        if is_active is not None:
            params["is_active"] = "eq.true" if is_active else "eq.false"
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(
                f"{self._base_url}/rest/v1/salon_services",
                headers=self._headers(actor, organization_id, business_id),
                params=params,
            )
            self._handle_error(resp, context="list_services")
            return [self._to_service(r) for r in resp.json()]

    async def update_service(
        self,
        actor: AuthenticatedUser,
        organization_id: UUID,
        business_id: UUID,
        service_id: UUID,
        payload: SalonServiceUpdateRequest,
    ) -> SalonServiceResponse:
        updates = payload.model_dump(exclude_unset=True)
        if not updates:
            return await self.get_service(actor, organization_id, business_id, service_id)
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.patch(
                f"{self._base_url}/rest/v1/salon_services",
                headers=self._headers(actor, organization_id, business_id),
                params={
                    "id": f"eq.{service_id}",
                    "organization_id": f"eq.{organization_id}",
                    "business_id": f"eq.{business_id}",
                },
                json=updates,
            )
            self._handle_error(resp, context="update_service")
            rows = resp.json()
            if not rows:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Salon service '{service_id}' was not found.",
                )
            return self._to_service(rows[0])

    async def delete_service(
        self,
        actor: AuthenticatedUser,
        organization_id: UUID,
        business_id: UUID,
        service_id: UUID,
    ) -> None:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.delete(
                f"{self._base_url}/rest/v1/salon_services",
                headers=self._headers(actor, organization_id, business_id),
                params={
                    "id": f"eq.{service_id}",
                    "organization_id": f"eq.{organization_id}",
                    "business_id": f"eq.{business_id}",
                },
            )
            self._handle_error(resp, context="delete_service")
            if not resp.json():
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Salon service '{service_id}' was not found.",
                )

    # =========================================================================
    # Staff & Service Assignments
    # =========================================================================

    @staticmethod
    def _to_break(row: Dict[str, Any]) -> SalonStaffBreakResponse:
        return SalonStaffBreakResponse(
            id=UUID(row["id"]),
            organization_id=UUID(row["organization_id"]),
            business_id=UUID(row["business_id"]),
            staff_id=UUID(row["staff_id"]),
            weekday=int(row["weekday"]) if row.get("weekday") is not None else None,
            specific_date=_parse_date(row.get("specific_date")),
            label=row["label"],
            start_time=normalize_time_string(row["start_time"]) or "00:00",
            end_time=normalize_time_string(row["end_time"]) or "00:00",
            created_at=_parse_dt(row["created_at"]),  # type: ignore[arg-type]
        )

    @staticmethod
    def _to_working_hours_item(row: Dict[str, Any]) -> SalonStaffWorkingHoursItem:
        is_off = bool(row["is_off"])
        return SalonStaffWorkingHoursItem(
            weekday=int(row["weekday"]),
            is_off=is_off,
            start_time=None if is_off else normalize_time_string(row.get("start_time")),
            end_time=None if is_off else normalize_time_string(row.get("end_time")),
        )

    @classmethod
    def _to_staff(cls, row: Dict[str, Any]) -> SalonStaffResponse:
        svc_links = row.get("salon_staff_services") or []
        assigned_ids: List[UUID] = []
        assigned_names: List[str] = []
        for link in svc_links:
            assigned_ids.append(UUID(link["service_id"]))
            svc_rel = link.get("salon_services")
            if isinstance(svc_rel, dict) and svc_rel.get("name"):
                assigned_names.append(str(svc_rel["name"]))

        wh_rows = row.get("salon_staff_working_hours") or []
        working_hours = (
            sorted(
                [cls._to_working_hours_item(w) for w in wh_rows],
                key=lambda x: x.weekday,
            )
            if wh_rows
            else _default_staff_working_hours()
        )
        break_rows = row.get("salon_staff_breaks") or []
        breaks = [cls._to_break(b) for b in break_rows]

        return SalonStaffResponse(
            id=UUID(row["id"]),
            organization_id=UUID(row["organization_id"]),
            business_id=UUID(row["business_id"]),
            full_name=row["full_name"],
            role_designation=row["role_designation"],
            email=row.get("email"),
            phone=row.get("phone"),
            bio=row.get("bio"),
            is_active=bool(row["is_active"]),
            assigned_service_ids=assigned_ids,
            assigned_service_names=assigned_names,
            working_hours=working_hours,
            breaks=breaks,
            created_at=_parse_dt(row["created_at"]),  # type: ignore[arg-type]
            updated_at=_parse_dt(row["updated_at"]),  # type: ignore[arg-type]
        )

    async def create_staff(
        self,
        actor: AuthenticatedUser,
        organization_id: UUID,
        business_id: UUID,
        payload: SalonStaffCreateRequest,
    ) -> SalonStaffResponse:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(
                f"{self._base_url}/rest/v1/salon_staff",
                headers=self._headers(actor, organization_id, business_id),
                json={
                    "organization_id": str(organization_id),
                    "business_id": str(business_id),
                    "full_name": payload.full_name,
                    "role_designation": payload.role_designation,
                    "email": payload.email,
                    "phone": payload.phone,
                    "bio": payload.bio,
                    "is_active": payload.is_active,
                },
            )
            self._handle_error(resp, context="create_staff")
            staff_id = UUID(resp.json()[0]["id"])

        try:
            # Seed default working hours in PostgreSQL
            await self.update_staff_working_hours(
                actor,
                organization_id,
                business_id,
                staff_id,
                SalonStaffWorkingHoursUpdateRequest(schedule=_default_staff_working_hours()),
            )
            if payload.assigned_service_ids:
                await self.assign_staff_services(
                    actor, organization_id, business_id, staff_id, payload.assigned_service_ids
                )
        except Exception:
            async with httpx.AsyncClient(timeout=10.0) as client:
                await client.delete(
                    f"{self._base_url}/rest/v1/salon_staff",
                    headers=self._headers(actor, organization_id, business_id, prefer="return=minimal"),
                    params={
                        "id": f"eq.{staff_id}",
                        "organization_id": f"eq.{organization_id}",
                        "business_id": f"eq.{business_id}",
                    },
                )
            raise

        return await self.get_staff(actor, organization_id, business_id, staff_id)

    async def get_staff(
        self,
        actor: AuthenticatedUser,
        organization_id: UUID,
        business_id: UUID,
        staff_id: UUID,
    ) -> SalonStaffResponse:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(
                f"{self._base_url}/rest/v1/salon_staff",
                headers=self._headers(actor, organization_id, business_id),
                params={
                    "select": self._STAFF_SELECT,
                    "id": f"eq.{staff_id}",
                    "organization_id": f"eq.{organization_id}",
                    "business_id": f"eq.{business_id}",
                },
            )
            self._handle_error(resp, context="get_staff")
            rows = resp.json()
            if not rows:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Salon staff member '{staff_id}' was not found.",
                )
            return self._to_staff(rows[0])

    async def list_staff(
        self,
        actor: AuthenticatedUser,
        organization_id: UUID,
        business_id: UUID,
        service_id: Optional[UUID] = None,
        is_active: Optional[bool] = None,
        limit: int = DEFAULT_PAGE_LIMIT,
        offset: int = 0,
    ) -> List[SalonStaffResponse]:
        bounded_limit, bounded_offset = _clamp_pagination(limit, offset)
        params: Dict[str, str] = {
            "select": self._STAFF_SELECT,
            "organization_id": f"eq.{organization_id}",
            "business_id": f"eq.{business_id}",
            "order": "full_name.asc",
            "limit": str(bounded_limit),
            "offset": str(bounded_offset),
        }
        if is_active is not None:
            params["is_active"] = "eq.true" if is_active else "eq.false"
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(
                f"{self._base_url}/rest/v1/salon_staff",
                headers=self._headers(actor, organization_id, business_id),
                params=params,
            )
            self._handle_error(resp, context="list_staff")
            staff_list = [self._to_staff(r) for r in resp.json()]
        if service_id is not None:
            staff_list = [s for s in staff_list if service_id in s.assigned_service_ids]
        return staff_list

    async def update_staff(
        self,
        actor: AuthenticatedUser,
        organization_id: UUID,
        business_id: UUID,
        staff_id: UUID,
        payload: SalonStaffUpdateRequest,
    ) -> SalonStaffResponse:
        updates = payload.model_dump(exclude_unset=True)
        assigned_service_ids = updates.pop("assigned_service_ids", None)
        if updates:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.patch(
                    f"{self._base_url}/rest/v1/salon_staff",
                    headers=self._headers(actor, organization_id, business_id),
                    params={
                        "id": f"eq.{staff_id}",
                        "organization_id": f"eq.{organization_id}",
                        "business_id": f"eq.{business_id}",
                    },
                    json=updates,
                )
                self._handle_error(resp, context="update_staff")
                if not resp.json():
                    raise HTTPException(
                        status_code=status.HTTP_404_NOT_FOUND,
                        detail=f"Salon staff member '{staff_id}' was not found.",
                    )
        if assigned_service_ids is not None:
            return await self.assign_staff_services(
                actor, organization_id, business_id, staff_id, assigned_service_ids
            )
        return await self.get_staff(actor, organization_id, business_id, staff_id)

    async def delete_staff(
        self,
        actor: AuthenticatedUser,
        organization_id: UUID,
        business_id: UUID,
        staff_id: UUID,
    ) -> None:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.delete(
                f"{self._base_url}/rest/v1/salon_staff",
                headers=self._headers(actor, organization_id, business_id),
                params={
                    "id": f"eq.{staff_id}",
                    "organization_id": f"eq.{organization_id}",
                    "business_id": f"eq.{business_id}",
                },
            )
            self._handle_error(resp, context="delete_staff")
            if not resp.json():
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Salon staff member '{staff_id}' was not found.",
                )

    async def assign_staff_services(
        self,
        actor: AuthenticatedUser,
        organization_id: UUID,
        business_id: UUID,
        staff_id: UUID,
        service_ids: List[UUID],
    ) -> SalonStaffResponse:
        # 1. Validate staff belongs to this (organization_id, business_id) before any DELETE
        await self.get_staff(actor, organization_id, business_id, staff_id)
        unique_ids = list(dict.fromkeys(service_ids))

        # 2. Validate EVERY requested service_id belongs to this same (organization_id, business_id)
        #    before deleting existing assignments to prevent destructive partial updates or cross-tenant IDs.
        if unique_ids:
            csv_ids = ",".join(str(sid) for sid in unique_ids)
            async with httpx.AsyncClient(timeout=10.0) as client:
                check_resp = await client.get(
                    f"{self._base_url}/rest/v1/salon_services",
                    headers=self._headers(actor, organization_id, business_id),
                    params={
                        "select": "id",
                        "organization_id": f"eq.{organization_id}",
                        "business_id": f"eq.{business_id}",
                        "id": f"in.({csv_ids})",
                    },
                )
                self._handle_error(check_resp, context="validate_staff_services")
                found_ids = {UUID(r["id"]) for r in check_resp.json()}
                missing = [str(sid) for sid in unique_ids if sid not in found_ids]
                if missing:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="One or more requested service_ids do not belong to this salon.",
                    )

        # Note: PostgREST does not support multi-statement HTTP transactions without a dedicated SQL RPC.
        # Pre-validating both staff and all service_ids above prevents cross-tenant or invalid-ID partial deletes.
        async with httpx.AsyncClient(timeout=10.0) as client:
            del_resp = await client.delete(
                f"{self._base_url}/rest/v1/salon_staff_services",
                headers=self._headers(actor, organization_id, business_id, prefer="return=minimal"),
                params={
                    "organization_id": f"eq.{organization_id}",
                    "business_id": f"eq.{business_id}",
                    "staff_id": f"eq.{staff_id}",
                },
            )
            self._handle_error(del_resp, context="delete_staff_services")
            if unique_ids:
                ins_resp = await client.post(
                    f"{self._base_url}/rest/v1/salon_staff_services",
                    headers=self._headers(actor, organization_id, business_id),
                    json=[
                        {
                            "organization_id": str(organization_id),
                            "business_id": str(business_id),
                            "staff_id": str(staff_id),
                            "service_id": str(sid),
                        }
                        for sid in unique_ids
                    ],
                )
                self._handle_error(ins_resp, context="assign_staff_services")
        return await self.get_staff(actor, organization_id, business_id, staff_id)

    # =========================================================================
    # Schedules & Breaks
    # =========================================================================

    async def update_staff_working_hours(
        self,
        actor: AuthenticatedUser,
        organization_id: UUID,
        business_id: UUID,
        staff_id: UUID,
        payload: SalonStaffWorkingHoursUpdateRequest,
    ) -> List[SalonStaffWorkingHoursItem]:
        rows = [
            {
                "organization_id": str(organization_id),
                "business_id": str(business_id),
                "staff_id": str(staff_id),
                "weekday": item.weekday,
                "is_off": item.is_off,
                "start_time": None if item.is_off else item.start_time,
                "end_time": None if item.is_off else item.end_time,
            }
            for item in payload.schedule
        ]
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(
                f"{self._base_url}/rest/v1/salon_staff_working_hours",
                headers=self._headers(
                    actor,
                    organization_id,
                    business_id,
                    prefer="resolution=merge-duplicates,return=representation",
                ),
                params={"on_conflict": "staff_id,weekday"},
                json=rows,
            )
            self._handle_error(resp, context="update_staff_working_hours")
        return await self.get_staff_working_hours(actor, organization_id, business_id, staff_id)

    async def get_staff_working_hours(
        self,
        actor: AuthenticatedUser,
        organization_id: UUID,
        business_id: UUID,
        staff_id: UUID,
    ) -> List[SalonStaffWorkingHoursItem]:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(
                f"{self._base_url}/rest/v1/salon_staff_working_hours",
                headers=self._headers(actor, organization_id, business_id),
                params={
                    "organization_id": f"eq.{organization_id}",
                    "business_id": f"eq.{business_id}",
                    "staff_id": f"eq.{staff_id}",
                    "order": "weekday.asc",
                },
            )
            self._handle_error(resp, context="get_staff_working_hours")
            rows = resp.json()
            if not rows:
                return _default_staff_working_hours()
            return [self._to_working_hours_item(r) for r in rows]

    async def add_staff_break(
        self,
        actor: AuthenticatedUser,
        organization_id: UUID,
        business_id: UUID,
        staff_id: UUID,
        payload: SalonStaffBreakCreateRequest,
    ) -> SalonStaffBreakResponse:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(
                f"{self._base_url}/rest/v1/salon_staff_breaks",
                headers=self._headers(actor, organization_id, business_id),
                json={
                    "organization_id": str(organization_id),
                    "business_id": str(business_id),
                    "staff_id": str(staff_id),
                    "weekday": payload.weekday,
                    "specific_date": payload.specific_date.isoformat()
                    if payload.specific_date
                    else None,
                    "label": payload.label,
                    "start_time": payload.start_time,
                    "end_time": payload.end_time,
                },
            )
            self._handle_error(resp, context="add_staff_break")
            return self._to_break(resp.json()[0])

    async def list_staff_breaks(
        self,
        actor: AuthenticatedUser,
        organization_id: UUID,
        business_id: UUID,
        staff_id: UUID,
    ) -> List[SalonStaffBreakResponse]:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(
                f"{self._base_url}/rest/v1/salon_staff_breaks",
                headers=self._headers(actor, organization_id, business_id),
                params={
                    "organization_id": f"eq.{organization_id}",
                    "business_id": f"eq.{business_id}",
                    "staff_id": f"eq.{staff_id}",
                },
            )
            self._handle_error(resp, context="list_staff_breaks")
            return [self._to_break(r) for r in resp.json()]

    async def delete_staff_break(
        self,
        actor: AuthenticatedUser,
        organization_id: UUID,
        business_id: UUID,
        staff_id: UUID,
        break_id: UUID,
    ) -> None:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.delete(
                f"{self._base_url}/rest/v1/salon_staff_breaks",
                headers=self._headers(actor, organization_id, business_id),
                params={
                    "id": f"eq.{break_id}",
                    "organization_id": f"eq.{organization_id}",
                    "business_id": f"eq.{business_id}",
                    "staff_id": f"eq.{staff_id}",
                },
            )
            self._handle_error(resp, context="delete_staff_break")
            if not resp.json():
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Staff break '{break_id}' was not found.",
                )

    # =========================================================================
    # Holidays & Closures
    # =========================================================================

    @staticmethod
    def _to_holiday(row: Dict[str, Any]) -> SalonHolidayResponse:
        is_all_day = bool(row["is_closed_all_day"])
        return SalonHolidayResponse(
            id=UUID(row["id"]),
            organization_id=UUID(row["organization_id"]),
            business_id=UUID(row["business_id"]),
            staff_id=UUID(row["staff_id"]) if row.get("staff_id") else None,
            holiday_date=_parse_date(row["holiday_date"]),  # type: ignore[arg-type]
            title=row["title"],
            is_closed_all_day=is_all_day,
            start_time=None if is_all_day else normalize_time_string(row.get("start_time")),
            end_time=None if is_all_day else normalize_time_string(row.get("end_time")),
            created_at=_parse_dt(row["created_at"]),  # type: ignore[arg-type]
        )

    async def create_holiday(
        self,
        actor: AuthenticatedUser,
        organization_id: UUID,
        business_id: UUID,
        payload: SalonHolidayCreateRequest,
    ) -> SalonHolidayResponse:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(
                f"{self._base_url}/rest/v1/salon_holidays",
                headers=self._headers(actor, organization_id, business_id),
                json={
                    "organization_id": str(organization_id),
                    "business_id": str(business_id),
                    "staff_id": str(payload.staff_id) if payload.staff_id else None,
                    "holiday_date": payload.holiday_date.isoformat(),
                    "title": payload.title,
                    "is_closed_all_day": payload.is_closed_all_day,
                    "start_time": None if payload.is_closed_all_day else payload.start_time,
                    "end_time": None if payload.is_closed_all_day else payload.end_time,
                },
            )
            self._handle_error(resp, context="create_holiday")
            return self._to_holiday(resp.json()[0])

    async def list_holidays(
        self,
        actor: AuthenticatedUser,
        organization_id: UUID,
        business_id: UUID,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        limit: int = DEFAULT_PAGE_LIMIT,
        offset: int = 0,
    ) -> List[SalonHolidayResponse]:
        bounded_limit, bounded_offset = _clamp_pagination(limit, offset)
        params: List[tuple[str, str]] = [
            ("organization_id", f"eq.{organization_id}"),
            ("business_id", f"eq.{business_id}"),
            ("order", "holiday_date.asc"),
            ("limit", str(bounded_limit)),
            ("offset", str(bounded_offset)),
        ]
        if start_date is not None:
            params.append(("holiday_date", f"gte.{start_date.isoformat()}"))
        if end_date is not None:
            params.append(("holiday_date", f"lte.{end_date.isoformat()}"))
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(
                f"{self._base_url}/rest/v1/salon_holidays",
                headers=self._headers(actor, organization_id, business_id),
                params=params,
            )
            self._handle_error(resp, context="list_holidays")
            return [self._to_holiday(r) for r in resp.json()]

    async def delete_holiday(
        self,
        actor: AuthenticatedUser,
        organization_id: UUID,
        business_id: UUID,
        holiday_id: UUID,
    ) -> None:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.delete(
                f"{self._base_url}/rest/v1/salon_holidays",
                headers=self._headers(actor, organization_id, business_id),
                params={
                    "id": f"eq.{holiday_id}",
                    "organization_id": f"eq.{organization_id}",
                    "business_id": f"eq.{business_id}",
                },
            )
            self._handle_error(resp, context="delete_holiday")
            if not resp.json():
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Salon holiday '{holiday_id}' was not found.",
                )

    # =========================================================================
    # Appointments (PostgreSQL GiST Exclusion + Idempotency)
    # =========================================================================

    @staticmethod
    def _to_appointment(
        row: Dict[str, Any], *, fallback: Optional[SalonAppointmentResponse] = None
    ) -> SalonAppointmentResponse:
        svc_rel = row.get("salon_services") or {}
        st_rel = row.get("salon_staff") or {}
        return SalonAppointmentResponse(
            id=UUID(row["id"]),
            organization_id=UUID(row["organization_id"]),
            business_id=UUID(row["business_id"]),
            booking_reference=row["booking_reference"],
            idempotency_key=row.get("idempotency_key"),
            service_id=UUID(row["service_id"]),
            service_name=(
                str(svc_rel["name"])
                if isinstance(svc_rel, dict) and svc_rel.get("name")
                else (fallback.service_name if fallback else "Service")
            ),
            service_duration_minutes=(
                int(svc_rel["duration_minutes"])
                if isinstance(svc_rel, dict) and svc_rel.get("duration_minutes") is not None
                else (fallback.service_duration_minutes if fallback else 30)
            ),
            service_price=(
                float(svc_rel["price"])
                if isinstance(svc_rel, dict) and svc_rel.get("price") is not None
                else (fallback.service_price if fallback else 0.0)
            ),
            service_currency=(
                str(svc_rel["currency"])
                if isinstance(svc_rel, dict) and svc_rel.get("currency")
                else (fallback.service_currency if fallback else "INR")
            ),
            staff_id=UUID(row["staff_id"]),
            staff_name=(
                str(st_rel["full_name"])
                if isinstance(st_rel, dict) and st_rel.get("full_name")
                else (fallback.staff_name if fallback else "Stylist")
            ),
            staff_role=(
                str(st_rel["role_designation"])
                if isinstance(st_rel, dict) and st_rel.get("role_designation")
                else (fallback.staff_role if fallback else "Stylist")
            ),
            customer_name=row["customer_name"],
            customer_phone=row["customer_phone"],
            customer_email=row.get("customer_email"),
            notes=row.get("notes"),
            appointment_date=_parse_date(row["appointment_date"]),  # type: ignore[arg-type]
            start_time=normalize_time_string(row["start_time"]) or "00:00",
            end_time=normalize_time_string(row["end_time"]) or "00:00",
            start_at=_parse_dt(row["start_at"]),  # type: ignore[arg-type]
            end_at=_parse_dt(row["end_at"]),  # type: ignore[arg-type]
            timezone=row["timezone"],
            status=SalonAppointmentStatus(row["status"]),
            source=SalonAppointmentSource(row["source"]),
            cancelled_at=_parse_dt(row.get("cancelled_at")),
            cancellation_reason=row.get("cancellation_reason"),
            created_at=_parse_dt(row["created_at"]),  # type: ignore[arg-type]
            updated_at=_parse_dt(row["updated_at"]),  # type: ignore[arg-type]
        )

    async def create_appointment(
        self,
        actor: AuthenticatedUser,
        organization_id: UUID,
        business_id: UUID,
        appointment: SalonAppointmentResponse,
    ) -> SalonAppointmentResponse:
        if appointment.idempotency_key:
            existing = await self.get_appointment_by_idempotency_key(
                actor, organization_id, business_id, appointment.idempotency_key
            )
            if existing:
                return existing

        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(
                f"{self._base_url}/rest/v1/salon_appointments",
                headers=self._headers(actor, organization_id, business_id),
                params={"select": self._APPT_SELECT},
                json={
                    "id": str(appointment.id),
                    "organization_id": str(organization_id),
                    "business_id": str(business_id),
                    "booking_reference": appointment.booking_reference,
                    "idempotency_key": appointment.idempotency_key,
                    "service_id": str(appointment.service_id),
                    "staff_id": str(appointment.staff_id),
                    "customer_name": appointment.customer_name,
                    "customer_phone": appointment.customer_phone,
                    "customer_email": appointment.customer_email,
                    "notes": appointment.notes,
                    "appointment_date": appointment.appointment_date.isoformat(),
                    "start_time": appointment.start_time,
                    "end_time": appointment.end_time,
                    "start_at": appointment.start_at.astimezone(timezone.utc).isoformat(),
                    "end_at": appointment.end_at.astimezone(timezone.utc).isoformat(),
                    "timezone": appointment.timezone,
                    "status": appointment.status.value,
                    "source": appointment.source.value,
                },
            )
            if resp.status_code == 409 and appointment.idempotency_key:
                try:
                    body = resp.json()
                except Exception:
                    body = {}
                if str(body.get("code") or "") == "23505" and "idempotency" in str(
                    body.get("message") or ""
                ).lower():
                    replayed = await self.get_appointment_by_idempotency_key(
                        actor, organization_id, business_id, appointment.idempotency_key
                    )
                    if replayed:
                        return replayed
            self._handle_error(resp, context="create_appointment")
            return self._to_appointment(resp.json()[0], fallback=appointment)

    async def get_appointment(
        self,
        actor: AuthenticatedUser,
        organization_id: UUID,
        business_id: UUID,
        appointment_id: UUID,
    ) -> SalonAppointmentResponse:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(
                f"{self._base_url}/rest/v1/salon_appointments",
                headers=self._headers(actor, organization_id, business_id),
                params={
                    "select": self._APPT_SELECT,
                    "id": f"eq.{appointment_id}",
                    "organization_id": f"eq.{organization_id}",
                    "business_id": f"eq.{business_id}",
                },
            )
            self._handle_error(resp, context="get_appointment")
            rows = resp.json()
            if not rows:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Salon appointment '{appointment_id}' was not found.",
                )
            return self._to_appointment(rows[0])

    async def get_appointment_by_idempotency_key(
        self,
        actor: AuthenticatedUser,
        organization_id: UUID,
        business_id: UUID,
        idempotency_key: str,
    ) -> Optional[SalonAppointmentResponse]:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(
                f"{self._base_url}/rest/v1/salon_appointments",
                headers=self._headers(actor, organization_id, business_id),
                params={
                    "select": self._APPT_SELECT,
                    "organization_id": f"eq.{organization_id}",
                    "business_id": f"eq.{business_id}",
                    "idempotency_key": f"eq.{idempotency_key}",
                },
            )
            self._handle_error(resp, context="get_appointment_by_idempotency_key")
            rows = resp.json()
            return self._to_appointment(rows[0]) if rows else None

    async def list_appointments(
        self,
        actor: AuthenticatedUser,
        organization_id: UUID,
        business_id: UUID,
        appointment_date: Optional[date] = None,
        staff_id: Optional[UUID] = None,
        status: Optional[SalonAppointmentStatus] = None,
        limit: int = DEFAULT_PAGE_LIMIT,
        offset: int = 0,
    ) -> List[SalonAppointmentResponse]:
        bounded_limit, bounded_offset = _clamp_pagination(limit, offset)
        params: Dict[str, str] = {
            "select": self._APPT_SELECT,
            "organization_id": f"eq.{organization_id}",
            "business_id": f"eq.{business_id}",
            "order": "appointment_date.asc,start_time.asc",
            "limit": str(bounded_limit),
            "offset": str(bounded_offset),
        }
        if appointment_date is not None:
            params["appointment_date"] = f"eq.{appointment_date.isoformat()}"
        if staff_id is not None:
            params["staff_id"] = f"eq.{staff_id}"
        if status is not None:
            params["status"] = f"eq.{status.value}"
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(
                f"{self._base_url}/rest/v1/salon_appointments",
                headers=self._headers(actor, organization_id, business_id),
                params=params,
            )
            self._handle_error(resp, context="list_appointments")
            return [self._to_appointment(r) for r in resp.json()]

    async def update_appointment(
        self,
        actor: AuthenticatedUser,
        organization_id: UUID,
        business_id: UUID,
        appointment: SalonAppointmentResponse,
    ) -> SalonAppointmentResponse:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.patch(
                f"{self._base_url}/rest/v1/salon_appointments",
                headers=self._headers(actor, organization_id, business_id),
                params={
                    "select": self._APPT_SELECT,
                    "id": f"eq.{appointment.id}",
                    "organization_id": f"eq.{organization_id}",
                    "business_id": f"eq.{business_id}",
                },
                json={
                    "staff_id": str(appointment.staff_id),
                    "notes": appointment.notes,
                    "appointment_date": appointment.appointment_date.isoformat(),
                    "start_time": appointment.start_time,
                    "end_time": appointment.end_time,
                    "start_at": appointment.start_at.astimezone(timezone.utc).isoformat(),
                    "end_at": appointment.end_at.astimezone(timezone.utc).isoformat(),
                    "timezone": appointment.timezone,
                    "status": appointment.status.value,
                    "cancelled_at": (
                        appointment.cancelled_at.astimezone(timezone.utc).isoformat()
                        if appointment.cancelled_at
                        else None
                    ),
                    "cancellation_reason": appointment.cancellation_reason,
                },
            )
            self._handle_error(resp, context="update_appointment")
            rows = resp.json()
            if not rows:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Salon appointment '{appointment.id}' was not found.",
                )
            return self._to_appointment(rows[0], fallback=appointment)
