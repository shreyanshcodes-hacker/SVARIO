"""Stage 6 Clinic Workflow Module — Production Supabase PostgreSQL Repository.

Implements `ClinicRepositoryProtocol` against live Supabase PostgREST (`/rest/v1/*`):
- Forwards authenticated user JWTs so PostgreSQL Row Level Security (RLS) is enforced
  on every read and write.
- For verified internal voice agent sessions (`https://svario.internal/auth/v1`),
  uses `SUPABASE_SERVICE_ROLE_KEY` strictly scoped by backend-resolved
  `(organization_id, business_id)` filters, and fails closed if unconfigured.
- Preserves PostgreSQL `btree_gist` exclusion constraint (`23P01`) for double-booking
  prevention and partial unique index (`23505`) for appointment idempotency.
"""

from __future__ import annotations

from contextvars import ContextVar
from datetime import date, datetime, time, timezone
from decimal import Decimal
from typing import Any, Dict, List, Optional
from uuid import UUID, uuid4
import httpx
from fastapi import HTTPException, status
from app.core.auth import AuthenticatedUser
from app.core.config import Settings
from app.modules.clinics.repository import ClinicConflictError, ClinicNotFoundError
from app.modules.clinics.schemas import (
    ClinicAppointmentCreateRequest,
    ClinicAppointmentResponse,
    ClinicAppointmentSource,
    ClinicAppointmentStatus,
    ClinicConsultationTypeCreateRequest,
    ClinicConsultationTypeResponse,
    ClinicConsultationTypeUpdateRequest,
    ClinicDepartmentCreateRequest,
    ClinicDepartmentResponse,
    ClinicDepartmentUpdateRequest,
    ClinicDoctorCreateRequest,
    ClinicDoctorResponse,
    ClinicDoctorUpdateRequest,
    ClinicSpecialityCreateRequest,
    ClinicSpecialityResponse,
    ClinicSpecialityUpdateRequest,
    ConsultationMode,
    DoctorBreakCreateRequest,
    DoctorBreakResponse,
    DoctorUnavailabilityCreateRequest,
    DoctorUnavailabilityResponse,
    DoctorWorkingHoursItem,
    DoctorWorkingHoursResponse,
)

INTERNAL_VOICE_ISSUER = "https://svario.internal/auth/v1"

_current_clinic_actor: ContextVar[Optional[AuthenticatedUser]] = ContextVar(
    "svario_current_clinic_actor", default=None
)


def set_current_clinic_actor(actor: Optional[AuthenticatedUser]) -> None:
    """Bind the verified request actor to the current async task context."""
    _current_clinic_actor.set(actor)


def get_current_clinic_actor() -> Optional[AuthenticatedUser]:
    """Return the verified request actor bound to the current async task context."""
    return _current_clinic_actor.get()


def _parse_dt(val: Optional[str]) -> Optional[datetime]:
    if not val:
        return None
    return datetime.fromisoformat(val.replace("Z", "+00:00"))


def _parse_time(val: Optional[str]) -> Optional[time]:
    if not val:
        return None
    return time.fromisoformat(val)


def _parse_date(val: Optional[str]) -> Optional[date]:
    if not val:
        return None
    return date.fromisoformat(val)


class SupabaseRestClinicRepository:
    """Production Supabase PostgreSQL repository implementing ClinicRepositoryProtocol."""

    def __init__(self, settings: Settings) -> None:
        if not settings.is_live_supabase_configured or not settings.supabase_url or not settings.supabase_anon_key:
            raise RuntimeError(
                "SupabaseRestClinicRepository requires SUPABASE_URL and SUPABASE_ANON_KEY."
            )
        self._settings = settings
        self._base_url = settings.supabase_url.strip().rstrip("/")
        self._anon_key = settings.supabase_anon_key.strip()
        self._service_role_key = (
            settings.supabase_service_role_key.strip()
            if settings.supabase_service_role_key
            else None
        )

    def _headers(self, *, prefer: str = "return=representation") -> Dict[str, str]:
        actor = get_current_clinic_actor()
        if actor is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Authenticated actor context required for clinic database access.",
            )
        if actor.issuer == INTERNAL_VOICE_ISSUER:
            if not self._service_role_key:
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail="Voice agent database persistence is not configured on the server.",
                )
            token = self._service_role_key
            apikey = self._service_role_key
        else:
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
        if pg_code == "23P01" or "excl_clinic_appointments_no_doctor_overlap" in msg:
            raise ClinicConflictError(
                "Selected time slot is no longer available for this doctor."
            )
        if pg_code == "23505" or resp.status_code == 409:
            raise ClinicConflictError(f"Resource conflict during {context}.")
        if resp.status_code in {401, 403}:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Database access denied by tenant policy.",
            )
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Clinic persistence error during {context}.",
        )

    # ---- Departments ----
    @staticmethod
    def _to_department(row: Dict[str, Any]) -> ClinicDepartmentResponse:
        return ClinicDepartmentResponse(
            id=UUID(row["id"]),
            organization_id=UUID(row["organization_id"]),
            business_id=UUID(row["business_id"]),
            name=row["name"],
            description=row.get("description"),
            is_active=bool(row["is_active"]),
            created_at=_parse_dt(row["created_at"]),  # type: ignore[arg-type]
            updated_at=_parse_dt(row["updated_at"]),  # type: ignore[arg-type]
        )

    async def list_departments(
        self, organization_id: UUID, business_id: UUID, active_only: bool = False
    ) -> List[ClinicDepartmentResponse]:
        params: Dict[str, str] = {
            "organization_id": f"eq.{organization_id}",
            "business_id": f"eq.{business_id}",
            "order": "name.asc",
        }
        if active_only:
            params["is_active"] = "eq.true"
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(
                f"{self._base_url}/rest/v1/clinic_departments",
                headers=self._headers(),
                params=params,
            )
            self._handle_error(resp, context="list_departments")
            return [self._to_department(r) for r in resp.json()]

    async def get_department(
        self, organization_id: UUID, business_id: UUID, department_id: UUID
    ) -> Optional[ClinicDepartmentResponse]:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(
                f"{self._base_url}/rest/v1/clinic_departments",
                headers=self._headers(),
                params={
                    "id": f"eq.{department_id}",
                    "organization_id": f"eq.{organization_id}",
                    "business_id": f"eq.{business_id}",
                },
            )
            self._handle_error(resp, context="get_department")
            rows = resp.json()
            return self._to_department(rows[0]) if rows else None

    async def create_department(
        self, organization_id: UUID, business_id: UUID, payload: ClinicDepartmentCreateRequest
    ) -> ClinicDepartmentResponse:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(
                f"{self._base_url}/rest/v1/clinic_departments",
                headers=self._headers(),
                json={
                    "organization_id": str(organization_id),
                    "business_id": str(business_id),
                    "name": payload.name.strip(),
                    "description": payload.description.strip() if payload.description else None,
                    "is_active": payload.is_active,
                },
            )
            self._handle_error(resp, context="create_department")
            return self._to_department(resp.json()[0])

    async def update_department(
        self,
        organization_id: UUID,
        business_id: UUID,
        department_id: UUID,
        payload: ClinicDepartmentUpdateRequest,
    ) -> Optional[ClinicDepartmentResponse]:
        updates = payload.model_dump(exclude_unset=True)
        if "name" in updates and updates["name"] is not None:
            updates["name"] = updates["name"].strip()
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.patch(
                f"{self._base_url}/rest/v1/clinic_departments",
                headers=self._headers(),
                params={
                    "id": f"eq.{department_id}",
                    "organization_id": f"eq.{organization_id}",
                    "business_id": f"eq.{business_id}",
                },
                json=updates,
            )
            self._handle_error(resp, context="update_department")
            rows = resp.json()
            return self._to_department(rows[0]) if rows else None

    # ---- Specialities ----
    @staticmethod
    def _to_speciality(row: Dict[str, Any]) -> ClinicSpecialityResponse:
        return ClinicSpecialityResponse(
            id=UUID(row["id"]),
            organization_id=UUID(row["organization_id"]),
            business_id=UUID(row["business_id"]),
            name=row["name"],
            description=row.get("description"),
            is_active=bool(row["is_active"]),
            created_at=_parse_dt(row["created_at"]),  # type: ignore[arg-type]
            updated_at=_parse_dt(row["updated_at"]),  # type: ignore[arg-type]
        )

    async def list_specialities(
        self, organization_id: UUID, business_id: UUID, active_only: bool = False
    ) -> List[ClinicSpecialityResponse]:
        params: Dict[str, str] = {
            "organization_id": f"eq.{organization_id}",
            "business_id": f"eq.{business_id}",
            "order": "name.asc",
        }
        if active_only:
            params["is_active"] = "eq.true"
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(
                f"{self._base_url}/rest/v1/clinic_specialities",
                headers=self._headers(),
                params=params,
            )
            self._handle_error(resp, context="list_specialities")
            return [self._to_speciality(r) for r in resp.json()]

    async def get_speciality(
        self, organization_id: UUID, business_id: UUID, speciality_id: UUID
    ) -> Optional[ClinicSpecialityResponse]:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(
                f"{self._base_url}/rest/v1/clinic_specialities",
                headers=self._headers(),
                params={
                    "id": f"eq.{speciality_id}",
                    "organization_id": f"eq.{organization_id}",
                    "business_id": f"eq.{business_id}",
                },
            )
            self._handle_error(resp, context="get_speciality")
            rows = resp.json()
            return self._to_speciality(rows[0]) if rows else None

    async def create_speciality(
        self, organization_id: UUID, business_id: UUID, payload: ClinicSpecialityCreateRequest
    ) -> ClinicSpecialityResponse:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(
                f"{self._base_url}/rest/v1/clinic_specialities",
                headers=self._headers(),
                json={
                    "organization_id": str(organization_id),
                    "business_id": str(business_id),
                    "name": payload.name.strip(),
                    "description": payload.description.strip() if payload.description else None,
                    "is_active": payload.is_active,
                },
            )
            self._handle_error(resp, context="create_speciality")
            return self._to_speciality(resp.json()[0])

    async def update_speciality(
        self,
        organization_id: UUID,
        business_id: UUID,
        speciality_id: UUID,
        payload: ClinicSpecialityUpdateRequest,
    ) -> Optional[ClinicSpecialityResponse]:
        updates = payload.model_dump(exclude_unset=True)
        if "name" in updates and updates["name"] is not None:
            updates["name"] = updates["name"].strip()
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.patch(
                f"{self._base_url}/rest/v1/clinic_specialities",
                headers=self._headers(),
                params={
                    "id": f"eq.{speciality_id}",
                    "organization_id": f"eq.{organization_id}",
                    "business_id": f"eq.{business_id}",
                },
                json=updates,
            )
            self._handle_error(resp, context="update_speciality")
            rows = resp.json()
            return self._to_speciality(rows[0]) if rows else None

    # ---- Consultation Types ----
    @staticmethod
    def _to_consultation_type(row: Dict[str, Any]) -> ClinicConsultationTypeResponse:
        fee = row.get("fee_amount")
        return ClinicConsultationTypeResponse(
            id=UUID(row["id"]),
            organization_id=UUID(row["organization_id"]),
            business_id=UUID(row["business_id"]),
            name=row["name"],
            description=row.get("description"),
            duration_minutes=int(row["duration_minutes"]),
            consultation_mode=ConsultationMode(row["consultation_mode"]),
            fee_amount=Decimal(str(fee)) if fee is not None else None,
            currency_code=row.get("currency_code"),
            is_active=bool(row["is_active"]),
            created_at=_parse_dt(row["created_at"]),  # type: ignore[arg-type]
            updated_at=_parse_dt(row["updated_at"]),  # type: ignore[arg-type]
        )

    async def list_consultation_types(
        self, organization_id: UUID, business_id: UUID, active_only: bool = False
    ) -> List[ClinicConsultationTypeResponse]:
        params: Dict[str, str] = {
            "organization_id": f"eq.{organization_id}",
            "business_id": f"eq.{business_id}",
            "order": "name.asc",
        }
        if active_only:
            params["is_active"] = "eq.true"
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(
                f"{self._base_url}/rest/v1/clinic_consultation_types",
                headers=self._headers(),
                params=params,
            )
            self._handle_error(resp, context="list_consultation_types")
            return [self._to_consultation_type(r) for r in resp.json()]

    async def get_consultation_type(
        self, organization_id: UUID, business_id: UUID, consultation_type_id: UUID
    ) -> Optional[ClinicConsultationTypeResponse]:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(
                f"{self._base_url}/rest/v1/clinic_consultation_types",
                headers=self._headers(),
                params={
                    "id": f"eq.{consultation_type_id}",
                    "organization_id": f"eq.{organization_id}",
                    "business_id": f"eq.{business_id}",
                },
            )
            self._handle_error(resp, context="get_consultation_type")
            rows = resp.json()
            return self._to_consultation_type(rows[0]) if rows else None

    async def create_consultation_type(
        self,
        organization_id: UUID,
        business_id: UUID,
        payload: ClinicConsultationTypeCreateRequest,
    ) -> ClinicConsultationTypeResponse:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(
                f"{self._base_url}/rest/v1/clinic_consultation_types",
                headers=self._headers(),
                json={
                    "organization_id": str(organization_id),
                    "business_id": str(business_id),
                    "name": payload.name.strip(),
                    "description": payload.description.strip() if payload.description else None,
                    "duration_minutes": payload.duration_minutes,
                    "consultation_mode": payload.consultation_mode.value,
                    "fee_amount": str(payload.fee_amount) if payload.fee_amount is not None else None,
                    "currency_code": payload.currency_code.upper() if payload.currency_code else None,
                    "is_active": payload.is_active,
                },
            )
            self._handle_error(resp, context="create_consultation_type")
            return self._to_consultation_type(resp.json()[0])

    async def update_consultation_type(
        self,
        organization_id: UUID,
        business_id: UUID,
        consultation_type_id: UUID,
        payload: ClinicConsultationTypeUpdateRequest,
    ) -> Optional[ClinicConsultationTypeResponse]:
        updates = payload.model_dump(exclude_unset=True)
        if "name" in updates and updates["name"] is not None:
            updates["name"] = updates["name"].strip()
        if "consultation_mode" in updates and updates["consultation_mode"] is not None:
            updates["consultation_mode"] = updates["consultation_mode"].value
        if "fee_amount" in updates and updates["fee_amount"] is not None:
            updates["fee_amount"] = str(updates["fee_amount"])
        if "currency_code" in updates and updates["currency_code"] is not None:
            updates["currency_code"] = updates["currency_code"].upper()
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.patch(
                f"{self._base_url}/rest/v1/clinic_consultation_types",
                headers=self._headers(),
                params={
                    "id": f"eq.{consultation_type_id}",
                    "organization_id": f"eq.{organization_id}",
                    "business_id": f"eq.{business_id}",
                },
                json=updates,
            )
            self._handle_error(resp, context="update_consultation_type")
            rows = resp.json()
            return self._to_consultation_type(rows[0]) if rows else None

    # ---- Doctors & Mappings ----
    @staticmethod
    def _to_doctor(row: Dict[str, Any]) -> ClinicDoctorResponse:
        dept_rows = row.get("clinic_doctor_departments") or []
        spec_rows = row.get("clinic_doctor_specialities") or []
        ct_rows = row.get("clinic_doctor_consultation_types") or []
        return ClinicDoctorResponse(
            id=UUID(row["id"]),
            organization_id=UUID(row["organization_id"]),
            business_id=UUID(row["business_id"]),
            display_name=row["display_name"],
            professional_title=row.get("professional_title"),
            public_bio=row.get("public_bio"),
            languages=list(row.get("languages") or ["en"]),
            is_active=bool(row["is_active"]),
            department_ids=[UUID(r["department_id"]) for r in dept_rows],
            speciality_ids=[UUID(r["speciality_id"]) for r in spec_rows],
            consultation_type_ids=[UUID(r["consultation_type_id"]) for r in ct_rows],
            created_at=_parse_dt(row["created_at"]),  # type: ignore[arg-type]
            updated_at=_parse_dt(row["updated_at"]),  # type: ignore[arg-type]
        )

    _DOCTOR_SELECT = (
        "*,clinic_doctor_departments(department_id),"
        "clinic_doctor_specialities(speciality_id),"
        "clinic_doctor_consultation_types(consultation_type_id)"
    )

    async def list_doctors(
        self, organization_id: UUID, business_id: UUID, active_only: bool = False
    ) -> List[ClinicDoctorResponse]:
        params: Dict[str, str] = {
            "select": self._DOCTOR_SELECT,
            "organization_id": f"eq.{organization_id}",
            "business_id": f"eq.{business_id}",
            "order": "display_name.asc",
        }
        if active_only:
            params["is_active"] = "eq.true"
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(
                f"{self._base_url}/rest/v1/clinic_doctors",
                headers=self._headers(),
                params=params,
            )
            self._handle_error(resp, context="list_doctors")
            return [self._to_doctor(r) for r in resp.json()]

    async def get_doctor(
        self, organization_id: UUID, business_id: UUID, doctor_id: UUID
    ) -> Optional[ClinicDoctorResponse]:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(
                f"{self._base_url}/rest/v1/clinic_doctors",
                headers=self._headers(),
                params={
                    "select": self._DOCTOR_SELECT,
                    "id": f"eq.{doctor_id}",
                    "organization_id": f"eq.{organization_id}",
                    "business_id": f"eq.{business_id}",
                },
            )
            self._handle_error(resp, context="get_doctor")
            rows = resp.json()
            return self._to_doctor(rows[0]) if rows else None

    async def create_doctor(
        self, organization_id: UUID, business_id: UUID, payload: ClinicDoctorCreateRequest
    ) -> ClinicDoctorResponse:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(
                f"{self._base_url}/rest/v1/clinic_doctors",
                headers=self._headers(),
                json={
                    "organization_id": str(organization_id),
                    "business_id": str(business_id),
                    "display_name": payload.display_name.strip(),
                    "professional_title": payload.professional_title.strip()
                    if payload.professional_title
                    else None,
                    "public_bio": payload.public_bio.strip() if payload.public_bio else None,
                    "languages": list(dict.fromkeys(payload.languages)),
                    "is_active": payload.is_active,
                },
            )
            self._handle_error(resp, context="create_doctor")
            doctor_id = UUID(resp.json()[0]["id"])

        try:
            if payload.department_ids:
                await self.set_doctor_departments(
                    organization_id, business_id, doctor_id, payload.department_ids
                )
            if payload.speciality_ids:
                await self.set_doctor_specialities(
                    organization_id, business_id, doctor_id, payload.speciality_ids
                )
            if payload.consultation_type_ids:
                await self.set_doctor_consultation_types(
                    organization_id, business_id, doctor_id, payload.consultation_type_ids
                )
        except Exception:
            # Compensating cleanup if mapping insertion fails
            async with httpx.AsyncClient(timeout=10.0) as client:
                await client.delete(
                    f"{self._base_url}/rest/v1/clinic_doctors",
                    headers=self._headers(prefer="return=minimal"),
                    params={
                        "id": f"eq.{doctor_id}",
                        "organization_id": f"eq.{organization_id}",
                        "business_id": f"eq.{business_id}",
                    },
                )
            raise

        created = await self.get_doctor(organization_id, business_id, doctor_id)
        assert created is not None
        return created

    async def update_doctor(
        self,
        organization_id: UUID,
        business_id: UUID,
        doctor_id: UUID,
        payload: ClinicDoctorUpdateRequest,
    ) -> Optional[ClinicDoctorResponse]:
        updates = payload.model_dump(exclude_unset=True)
        if "display_name" in updates and updates["display_name"] is not None:
            updates["display_name"] = updates["display_name"].strip()
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.patch(
                f"{self._base_url}/rest/v1/clinic_doctors",
                headers=self._headers(),
                params={
                    "id": f"eq.{doctor_id}",
                    "organization_id": f"eq.{organization_id}",
                    "business_id": f"eq.{business_id}",
                },
                json=updates,
            )
            self._handle_error(resp, context="update_doctor")
            if not resp.json():
                return None
        return await self.get_doctor(organization_id, business_id, doctor_id)

    async def _replace_mapping(
        self,
        *,
        table: str,
        target_col: str,
        organization_id: UUID,
        business_id: UUID,
        doctor_id: UUID,
        target_ids: List[UUID],
    ) -> Optional[ClinicDoctorResponse]:
        existing = await self.get_doctor(organization_id, business_id, doctor_id)
        if not existing:
            return None
        async with httpx.AsyncClient(timeout=10.0) as client:
            del_resp = await client.delete(
                f"{self._base_url}/rest/v1/{table}",
                headers=self._headers(prefer="return=minimal"),
                params={
                    "organization_id": f"eq.{organization_id}",
                    "business_id": f"eq.{business_id}",
                    "doctor_id": f"eq.{doctor_id}",
                },
            )
            self._handle_error(del_resp, context=f"delete_{table}")
            unique_ids = list(dict.fromkeys(target_ids))
            if unique_ids:
                ins_resp = await client.post(
                    f"{self._base_url}/rest/v1/{table}",
                    headers=self._headers(),
                    json=[
                        {
                            "organization_id": str(organization_id),
                            "business_id": str(business_id),
                            "doctor_id": str(doctor_id),
                            target_col: str(tid),
                        }
                        for tid in unique_ids
                    ],
                )
                self._handle_error(ins_resp, context=f"insert_{table}")
        return await self.get_doctor(organization_id, business_id, doctor_id)

    async def set_doctor_departments(
        self, organization_id: UUID, business_id: UUID, doctor_id: UUID, department_ids: List[UUID]
    ) -> Optional[ClinicDoctorResponse]:
        return await self._replace_mapping(
            table="clinic_doctor_departments",
            target_col="department_id",
            organization_id=organization_id,
            business_id=business_id,
            doctor_id=doctor_id,
            target_ids=department_ids,
        )

    async def set_doctor_specialities(
        self, organization_id: UUID, business_id: UUID, doctor_id: UUID, speciality_ids: List[UUID]
    ) -> Optional[ClinicDoctorResponse]:
        return await self._replace_mapping(
            table="clinic_doctor_specialities",
            target_col="speciality_id",
            organization_id=organization_id,
            business_id=business_id,
            doctor_id=doctor_id,
            target_ids=speciality_ids,
        )

    async def set_doctor_consultation_types(
        self,
        organization_id: UUID,
        business_id: UUID,
        doctor_id: UUID,
        consultation_type_ids: List[UUID],
    ) -> Optional[ClinicDoctorResponse]:
        return await self._replace_mapping(
            table="clinic_doctor_consultation_types",
            target_col="consultation_type_id",
            organization_id=organization_id,
            business_id=business_id,
            doctor_id=doctor_id,
            target_ids=consultation_type_ids,
        )

    # ---- Schedules: Working Hours, Breaks, Unavailability ----
    @staticmethod
    def _to_working_hours(row: Dict[str, Any]) -> DoctorWorkingHoursResponse:
        return DoctorWorkingHoursResponse(
            id=UUID(row["id"]),
            organization_id=UUID(row["organization_id"]),
            business_id=UUID(row["business_id"]),
            doctor_id=UUID(row["doctor_id"]),
            day_of_week=int(row["day_of_week"]),
            start_time=_parse_time(row.get("start_time")),
            end_time=_parse_time(row.get("end_time")),
            is_active=bool(row["is_active"]),
            created_at=_parse_dt(row["created_at"]),  # type: ignore[arg-type]
            updated_at=_parse_dt(row["updated_at"]),  # type: ignore[arg-type]
        )

    async def get_doctor_working_hours(
        self, organization_id: UUID, business_id: UUID, doctor_id: UUID
    ) -> List[DoctorWorkingHoursResponse]:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(
                f"{self._base_url}/rest/v1/clinic_doctor_working_hours",
                headers=self._headers(),
                params={
                    "organization_id": f"eq.{organization_id}",
                    "business_id": f"eq.{business_id}",
                    "doctor_id": f"eq.{doctor_id}",
                    "order": "day_of_week.asc",
                },
            )
            self._handle_error(resp, context="get_doctor_working_hours")
            return [self._to_working_hours(r) for r in resp.json()]

    async def upsert_doctor_working_hours(
        self,
        organization_id: UUID,
        business_id: UUID,
        doctor_id: UUID,
        items: List[DoctorWorkingHoursItem],
    ) -> List[DoctorWorkingHoursResponse]:
        rows = [
            {
                "organization_id": str(organization_id),
                "business_id": str(business_id),
                "doctor_id": str(doctor_id),
                "day_of_week": item.day_of_week,
                "start_time": item.start_time.isoformat() if item.is_active and item.start_time else None,
                "end_time": item.end_time.isoformat() if item.is_active and item.end_time else None,
                "is_active": item.is_active,
            }
            for item in items
        ]
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(
                f"{self._base_url}/rest/v1/clinic_doctor_working_hours",
                headers=self._headers(prefer="resolution=merge-duplicates,return=representation"),
                params={"on_conflict": "doctor_id,day_of_week"},
                json=rows,
            )
            self._handle_error(resp, context="upsert_doctor_working_hours")
        return await self.get_doctor_working_hours(organization_id, business_id, doctor_id)

    @staticmethod
    def _to_break(row: Dict[str, Any]) -> DoctorBreakResponse:
        return DoctorBreakResponse(
            id=UUID(row["id"]),
            organization_id=UUID(row["organization_id"]),
            business_id=UUID(row["business_id"]),
            doctor_id=UUID(row["doctor_id"]),
            day_of_week=int(row["day_of_week"]) if row.get("day_of_week") is not None else None,
            specific_date=_parse_date(row.get("specific_date")),
            break_start=_parse_time(row["break_start"]),  # type: ignore[arg-type]
            break_end=_parse_time(row["break_end"]),  # type: ignore[arg-type]
            reason=row.get("reason"),
            created_at=_parse_dt(row["created_at"]),  # type: ignore[arg-type]
        )

    async def list_doctor_breaks(
        self, organization_id: UUID, business_id: UUID, doctor_id: UUID
    ) -> List[DoctorBreakResponse]:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(
                f"{self._base_url}/rest/v1/clinic_doctor_breaks",
                headers=self._headers(),
                params={
                    "organization_id": f"eq.{organization_id}",
                    "business_id": f"eq.{business_id}",
                    "doctor_id": f"eq.{doctor_id}",
                },
            )
            self._handle_error(resp, context="list_doctor_breaks")
            return [self._to_break(r) for r in resp.json()]

    async def create_doctor_break(
        self,
        organization_id: UUID,
        business_id: UUID,
        doctor_id: UUID,
        payload: DoctorBreakCreateRequest,
    ) -> DoctorBreakResponse:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(
                f"{self._base_url}/rest/v1/clinic_doctor_breaks",
                headers=self._headers(),
                json={
                    "organization_id": str(organization_id),
                    "business_id": str(business_id),
                    "doctor_id": str(doctor_id),
                    "day_of_week": payload.day_of_week,
                    "specific_date": payload.specific_date.isoformat()
                    if payload.specific_date
                    else None,
                    "break_start": payload.break_start.isoformat(),
                    "break_end": payload.break_end.isoformat(),
                    "reason": payload.reason,
                },
            )
            self._handle_error(resp, context="create_doctor_break")
            return self._to_break(resp.json()[0])

    @staticmethod
    def _to_unavailability(row: Dict[str, Any]) -> DoctorUnavailabilityResponse:
        return DoctorUnavailabilityResponse(
            id=UUID(row["id"]),
            organization_id=UUID(row["organization_id"]),
            business_id=UUID(row["business_id"]),
            doctor_id=UUID(row["doctor_id"]),
            starts_at=_parse_dt(row["starts_at"]),  # type: ignore[arg-type]
            ends_at=_parse_dt(row["ends_at"]),  # type: ignore[arg-type]
            reason=row.get("reason"),
            created_at=_parse_dt(row["created_at"]),  # type: ignore[arg-type]
        )

    async def list_doctor_unavailability(
        self, organization_id: UUID, business_id: UUID, doctor_id: UUID
    ) -> List[DoctorUnavailabilityResponse]:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(
                f"{self._base_url}/rest/v1/clinic_doctor_unavailability",
                headers=self._headers(),
                params={
                    "organization_id": f"eq.{organization_id}",
                    "business_id": f"eq.{business_id}",
                    "doctor_id": f"eq.{doctor_id}",
                    "order": "starts_at.asc",
                },
            )
            self._handle_error(resp, context="list_doctor_unavailability")
            return [self._to_unavailability(r) for r in resp.json()]

    async def create_doctor_unavailability(
        self,
        organization_id: UUID,
        business_id: UUID,
        doctor_id: UUID,
        payload: DoctorUnavailabilityCreateRequest,
    ) -> DoctorUnavailabilityResponse:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(
                f"{self._base_url}/rest/v1/clinic_doctor_unavailability",
                headers=self._headers(),
                json={
                    "organization_id": str(organization_id),
                    "business_id": str(business_id),
                    "doctor_id": str(doctor_id),
                    "starts_at": payload.starts_at.astimezone(timezone.utc).isoformat(),
                    "ends_at": payload.ends_at.astimezone(timezone.utc).isoformat(),
                    "reason": payload.reason,
                },
            )
            self._handle_error(resp, context="create_doctor_unavailability")
            return self._to_unavailability(resp.json()[0])

    # ---- Appointments (PostgreSQL GiST Exclusion + Idempotency) ----
    _APPT_SELECT = (
        "*,clinic_doctors(display_name),clinic_consultation_types(name)"
    )

    @staticmethod
    def _to_appointment(row: Dict[str, Any]) -> ClinicAppointmentResponse:
        doc_rel = row.get("clinic_doctors") or {}
        ct_rel = row.get("clinic_consultation_types") or {}
        return ClinicAppointmentResponse(
            id=UUID(row["id"]),
            organization_id=UUID(row["organization_id"]),
            business_id=UUID(row["business_id"]),
            booking_reference=row["booking_reference"],
            doctor_id=UUID(row["doctor_id"]),
            doctor_name=doc_rel.get("display_name") if isinstance(doc_rel, dict) else None,
            consultation_type_id=UUID(row["consultation_type_id"]),
            consultation_type_name=ct_rel.get("name") if isinstance(ct_rel, dict) else None,
            department_id=UUID(row["department_id"]) if row.get("department_id") else None,
            patient_display_name=row["patient_display_name"],
            patient_contact=row["patient_contact"],
            starts_at=_parse_dt(row["starts_at"]),  # type: ignore[arg-type]
            ends_at=_parse_dt(row["ends_at"]),  # type: ignore[arg-type]
            timezone=row["timezone"],
            status=ClinicAppointmentStatus(row["status"]),
            source=ClinicAppointmentSource(row["source"]),
            cancellation_reason=row.get("cancellation_reason"),
            cancelled_at=_parse_dt(row.get("cancelled_at")),
            created_at=_parse_dt(row["created_at"]),  # type: ignore[arg-type]
            updated_at=_parse_dt(row["updated_at"]),  # type: ignore[arg-type]
        )

    async def list_appointments(
        self,
        organization_id: UUID,
        business_id: UUID,
        *,
        doctor_id: Optional[UUID] = None,
        target_date: Optional[date] = None,
        status_filter: Optional[ClinicAppointmentStatus] = None,
    ) -> List[ClinicAppointmentResponse]:
        params: Dict[str, str] = {
            "select": self._APPT_SELECT,
            "organization_id": f"eq.{organization_id}",
            "business_id": f"eq.{business_id}",
            "order": "starts_at.asc",
        }
        if doctor_id is not None:
            params["doctor_id"] = f"eq.{doctor_id}"
        if status_filter is not None:
            params["status"] = f"eq.{status_filter.value}"
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(
                f"{self._base_url}/rest/v1/clinic_appointments",
                headers=self._headers(),
                params=params,
            )
            self._handle_error(resp, context="list_appointments")
            items = [self._to_appointment(r) for r in resp.json()]
            if target_date is not None:
                items = [a for a in items if a.starts_at.date() == target_date]
            return items

    async def get_appointment(
        self, organization_id: UUID, business_id: UUID, appointment_id: UUID
    ) -> Optional[ClinicAppointmentResponse]:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(
                f"{self._base_url}/rest/v1/clinic_appointments",
                headers=self._headers(),
                params={
                    "select": self._APPT_SELECT,
                    "id": f"eq.{appointment_id}",
                    "organization_id": f"eq.{organization_id}",
                    "business_id": f"eq.{business_id}",
                },
            )
            self._handle_error(resp, context="get_appointment")
            rows = resp.json()
            return self._to_appointment(rows[0]) if rows else None

    async def get_appointment_by_reference(
        self, organization_id: UUID, business_id: UUID, booking_reference: str
    ) -> Optional[ClinicAppointmentResponse]:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(
                f"{self._base_url}/rest/v1/clinic_appointments",
                headers=self._headers(),
                params={
                    "select": self._APPT_SELECT,
                    "organization_id": f"eq.{organization_id}",
                    "business_id": f"eq.{business_id}",
                    "booking_reference": f"ilike.{booking_reference.strip()}",
                },
            )
            self._handle_error(resp, context="get_appointment_by_reference")
            rows = resp.json()
            return self._to_appointment(rows[0]) if rows else None

    async def _get_appointment_by_idempotency(
        self, organization_id: UUID, business_id: UUID, idempotency_key: str
    ) -> Optional[ClinicAppointmentResponse]:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(
                f"{self._base_url}/rest/v1/clinic_appointments",
                headers=self._headers(),
                params={
                    "select": self._APPT_SELECT,
                    "organization_id": f"eq.{organization_id}",
                    "business_id": f"eq.{business_id}",
                    "idempotency_key": f"eq.{idempotency_key}",
                },
            )
            self._handle_error(resp, context="get_appointment_by_idempotency")
            rows = resp.json()
            return self._to_appointment(rows[0]) if rows else None

    async def create_appointment_atomic(
        self,
        *,
        organization_id: UUID,
        business_id: UUID,
        payload: ClinicAppointmentCreateRequest,
        ends_at: datetime,
        tz_name: str,
        doctor_name: str,
        consultation_type_name: str,
    ) -> ClinicAppointmentResponse:
        if payload.idempotency_key:
            existing = await self._get_appointment_by_idempotency(
                organization_id, business_id, payload.idempotency_key
            )
            if existing:
                return existing

        appt_id = uuid4()
        booking_ref = f"CLN-{appt_id.hex[:8].upper()}"
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(
                f"{self._base_url}/rest/v1/clinic_appointments",
                headers=self._headers(),
                params={"select": self._APPT_SELECT},
                json={
                    "id": str(appt_id),
                    "organization_id": str(organization_id),
                    "business_id": str(business_id),
                    "booking_reference": booking_ref,
                    "doctor_id": str(payload.doctor_id),
                    "consultation_type_id": str(payload.consultation_type_id),
                    "department_id": str(payload.department_id) if payload.department_id else None,
                    "patient_display_name": payload.patient_display_name.strip(),
                    "patient_contact": payload.patient_contact.strip(),
                    "starts_at": payload.starts_at.astimezone(timezone.utc).isoformat(),
                    "ends_at": ends_at.astimezone(timezone.utc).isoformat(),
                    "timezone": tz_name,
                    "status": ClinicAppointmentStatus.CONFIRMED.value,
                    "source": payload.source.value,
                    "idempotency_key": payload.idempotency_key,
                },
            )
            if resp.status_code == 409 and payload.idempotency_key:
                try:
                    body = resp.json()
                except Exception:
                    body = {}
                if str(body.get("code") or "") == "23505" and "idempotency" in str(
                    body.get("message") or ""
                ).lower():
                    replayed = await self._get_appointment_by_idempotency(
                        organization_id, business_id, payload.idempotency_key
                    )
                    if replayed:
                        return replayed
            self._handle_error(resp, context="create_appointment")
            created = self._to_appointment(resp.json()[0])
            if not created.doctor_name:
                created = created.model_copy(update={"doctor_name": doctor_name})
            if not created.consultation_type_name:
                created = created.model_copy(
                    update={"consultation_type_name": consultation_type_name}
                )
            return created

    async def reschedule_appointment_atomic(
        self,
        *,
        organization_id: UUID,
        business_id: UUID,
        appointment_id: UUID,
        new_doctor_id: UUID,
        new_doctor_name: str,
        new_starts_at: datetime,
        new_ends_at: datetime,
    ) -> ClinicAppointmentResponse:
        existing = await self.get_appointment(organization_id, business_id, appointment_id)
        if not existing:
            raise ClinicNotFoundError("Appointment not found.")
        if existing.status == ClinicAppointmentStatus.CANCELLED:
            raise ClinicConflictError("Cancelled appointments cannot be rescheduled.")

        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.patch(
                f"{self._base_url}/rest/v1/clinic_appointments",
                headers=self._headers(),
                params={
                    "select": self._APPT_SELECT,
                    "id": f"eq.{appointment_id}",
                    "organization_id": f"eq.{organization_id}",
                    "business_id": f"eq.{business_id}",
                },
                json={
                    "doctor_id": str(new_doctor_id),
                    "starts_at": new_starts_at.astimezone(timezone.utc).isoformat(),
                    "ends_at": new_ends_at.astimezone(timezone.utc).isoformat(),
                    "status": ClinicAppointmentStatus.RESCHEDULED.value,
                },
            )
            self._handle_error(resp, context="reschedule_appointment")
            rows = resp.json()
            if not rows:
                raise ClinicNotFoundError("Appointment not found.")
            updated = self._to_appointment(rows[0])
            if not updated.doctor_name:
                updated = updated.model_copy(update={"doctor_name": new_doctor_name})
            return updated

    async def cancel_appointment_atomic(
        self,
        *,
        organization_id: UUID,
        business_id: UUID,
        appointment_id: UUID,
        reason: Optional[str],
    ) -> ClinicAppointmentResponse:
        existing = await self.get_appointment(organization_id, business_id, appointment_id)
        if not existing:
            raise ClinicNotFoundError("Appointment not found.")
        if existing.status == ClinicAppointmentStatus.CANCELLED:
            return existing

        now_iso = datetime.now(timezone.utc).isoformat()
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.patch(
                f"{self._base_url}/rest/v1/clinic_appointments",
                headers=self._headers(),
                params={
                    "select": self._APPT_SELECT,
                    "id": f"eq.{appointment_id}",
                    "organization_id": f"eq.{organization_id}",
                    "business_id": f"eq.{business_id}",
                },
                json={
                    "status": ClinicAppointmentStatus.CANCELLED.value,
                    "cancellation_reason": reason.strip() if reason else None,
                    "cancelled_at": now_iso,
                },
            )
            self._handle_error(resp, context="cancel_appointment")
            rows = resp.json()
            if not rows:
                raise ClinicNotFoundError("Appointment not found.")
            return self._to_appointment(rows[0])
