"""Idempotent demo seed script for 'Shreyansh salon'.

Usage (requires backend Supabase credentials in apps/api/.env; never commit secrets):
    cd apps/api
    python -m scripts.seed_shreyansh_salon_demo

Safety guarantees:
- Scoped strictly to Shreyansh salon (`organization_id`, `business_id`).
- Checks existing services and staff by case-insensitive trimmed name before inserting;
  running multiple times never creates duplicates and never deletes or overwrites
  existing records.
- Uses the existing `SalonWorkflowService` and verified internal actor.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Dict, List, Tuple
from uuid import UUID

from app.core.auth import AuthenticatedUser
from app.core.config import get_settings
from app.core.internal_voice import create_verified_internal_voice_actor
from app.modules.organizations.schemas import OrganizationIndustry
from app.modules.salons.schemas import (
    SalonServiceCreateRequest,
    SalonServiceResponse,
    SalonStaffCreateRequest,
    SalonStaffResponse,
    SalonStaffServiceAssignmentRequest,
    SalonStaffWorkingHoursItem,
    SalonStaffWorkingHoursUpdateRequest,
)
from app.modules.salons.service import SalonWorkflowService, build_salon_workflow_service

SHREYANSH_ORGANIZATION_ID = UUID("7e88145a-6157-4411-83a3-a817078bbb47")
SHREYANSH_BUSINESS_ID = UUID("8edfa502-4aad-424a-b8da-609fefef2a08")
SHREYANSH_OWNER_USER_ID = UUID("6ab206fd-a494-4415-b9e8-2ee52fa4dd1a")

SHREYANSH_DEMO_SERVICES: List[Dict[str, object]] = [
    {
        "name": "Classic Haircut",
        "category": "Hair",
        "duration_minutes": 30,
        "price": 299.0,
        "currency": "INR",
        "description": "Precision classic haircut with wash and neat finish.",
    },
    {
        "name": "Premium Haircut",
        "category": "Hair",
        "duration_minutes": 45,
        "price": 499.0,
        "currency": "INR",
        "description": "Tailored consultation haircut with relaxing wash and styling.",
    },
    {
        "name": "Hair Wash & Blow Dry",
        "category": "Hair",
        "duration_minutes": 30,
        "price": 399.0,
        "currency": "INR",
        "description": "Nourishing shampoo, conditioning rinse, and voluminous blow dry.",
    },
    {
        "name": "Hair Spa",
        "category": "Hair",
        "duration_minutes": 60,
        "price": 999.0,
        "currency": "INR",
        "description": "Deep conditioning hair spa ritual for hydration, shine, and scalp relaxation.",
    },
    {
        "name": "Beard Trim",
        "category": "Grooming",
        "duration_minutes": 20,
        "price": 199.0,
        "currency": "INR",
        "description": "Clean beard shaping, line-up, and soothing finish.",
    },
    {
        "name": "Haircut + Beard Combo",
        "category": "Grooming",
        "duration_minutes": 45,
        "price": 449.0,
        "currency": "INR",
        "description": "Complete classic haircut paired with precision beard styling.",
    },
    {
        "name": "Global Hair Colour",
        "category": "Hair Colour",
        "duration_minutes": 120,
        "price": 2499.0,
        "currency": "INR",
        "description": "Full-head rich hair colour application with gloss finish.",
    },
    {
        "name": "Hair Highlights",
        "category": "Hair Colour",
        "duration_minutes": 150,
        "price": 3499.0,
        "currency": "INR",
        "description": "Dimensional foil highlights tailored to skin tone and hair texture.",
    },
    {
        "name": "Basic Facial",
        "category": "Skin Care",
        "duration_minutes": 45,
        "price": 799.0,
        "currency": "INR",
        "description": "Gentle cleansing, exfoliation, massage, and hydrating mask.",
    },
    {
        "name": "Premium Facial",
        "category": "Skin Care",
        "duration_minutes": 60,
        "price": 1499.0,
        "currency": "INR",
        "description": "Advanced radiance facial with deep nourishment and lymphatic massage.",
    },
    {
        "name": "Cleanup",
        "category": "Skin Care",
        "duration_minutes": 30,
        "price": 499.0,
        "currency": "INR",
        "description": "Quick pore-refining skin cleanup for a fresh everyday glow.",
    },
    {
        "name": "Manicure",
        "category": "Nails",
        "duration_minutes": 40,
        "price": 399.0,
        "currency": "INR",
        "description": "Nail shaping, cuticle care, hand massage, and polish.",
    },
    {
        "name": "Pedicure",
        "category": "Nails",
        "duration_minutes": 45,
        "price": 499.0,
        "currency": "INR",
        "description": "Soothing foot soak, exfoliation, nail care, and polish.",
    },
    {
        "name": "Bridal Makeup",
        "category": "Makeup",
        "duration_minutes": 180,
        "price": 5999.0,
        "currency": "INR",
        "description": "Full bridal HD makeup, hair styling, and draping preparation.",
    },
    {
        "name": "Party Makeup",
        "category": "Makeup",
        "duration_minutes": 90,
        "price": 2499.0,
        "currency": "INR",
        "description": "Glamorous occasion makeup tailored to outfit and lighting.",
    },
]

SHREYANSH_DEMO_STAFF: List[Dict[str, object]] = [
    {
        "full_name": "Aarav Sharma",
        "role_designation": "Senior Hairstylist",
        "bio": "Specialisation: Haircuts, Hair Styling.",
        "services": ["Classic Haircut", "Premium Haircut", "Hair Wash & Blow Dry", "Hair Spa"],
    },
    {
        "full_name": "Riya Verma",
        "role_designation": "Beauty Specialist",
        "bio": "Specialisation: Facials, Cleanup, Skin Care.",
        "services": ["Basic Facial", "Premium Facial", "Cleanup"],
    },
    {
        "full_name": "Kabir Malhotra",
        "role_designation": "Grooming Expert",
        "bio": "Specialisation: Beard Styling, Haircuts.",
        "services": ["Classic Haircut", "Beard Trim", "Haircut + Beard Combo"],
    },
    {
        "full_name": "Ananya Singh",
        "role_designation": "Senior Makeup Artist",
        "bio": "Specialisation: Bridal Makeup, Party Makeup.",
        "services": ["Bridal Makeup", "Party Makeup"],
    },
    {
        "full_name": "Meera Kapoor",
        "role_designation": "Nail Technician",
        "bio": "Specialisation: Manicure, Pedicure.",
        "services": ["Manicure", "Pedicure"],
    },
    {
        "full_name": "Rahul Mehta",
        "role_designation": "Hair Colour Specialist",
        "bio": "Specialisation: Hair Colour, Highlights, Hair Spa.",
        "services": ["Global Hair Colour", "Hair Highlights", "Hair Spa"],
    },
]

DEFAULT_DEMO_WEEKLY_SCHEDULE: List[SalonStaffWorkingHoursItem] = [
    SalonStaffWorkingHoursItem(weekday=0, is_off=True, start_time=None, end_time=None),
    *[
        SalonStaffWorkingHoursItem(weekday=d, is_off=False, start_time="10:00", end_time="20:00")
        for d in range(1, 7)
    ],
]


async def seed_shreyansh_salon_demo(
    salon_service: SalonWorkflowService,
    actor: AuthenticatedUser,
) -> Dict[str, object]:
    """Idempotently seed services, staff, service mappings, and working hours for Shreyansh salon."""
    existing_services = await salon_service.list_services(
        actor=actor,
        organization_id=SHREYANSH_ORGANIZATION_ID,
        business_id=SHREYANSH_BUSINESS_ID,
        is_active=None,
    )
    service_by_name: Dict[str, SalonServiceResponse] = {
        svc.name.strip().lower(): svc for svc in existing_services
    }

    services_created: List[SalonServiceResponse] = []
    services_existing: List[SalonServiceResponse] = []

    for spec in SHREYANSH_DEMO_SERVICES:
        name = str(spec["name"])
        key = name.strip().lower()
        if key in service_by_name:
            services_existing.append(service_by_name[key])
            continue

        created = await salon_service.create_service(
            actor=actor,
            organization_id=SHREYANSH_ORGANIZATION_ID,
            business_id=SHREYANSH_BUSINESS_ID,
            payload=SalonServiceCreateRequest(
                name=name,
                description=str(spec["description"]),
                category=str(spec["category"]),
                price=float(spec["price"]),
                currency=str(spec["currency"]),
                duration_minutes=int(spec["duration_minutes"]),
                is_active=True,
            ),
        )
        services_created.append(created)
        service_by_name[key] = created

    existing_staff = await salon_service.list_staff(
        actor=actor,
        organization_id=SHREYANSH_ORGANIZATION_ID,
        business_id=SHREYANSH_BUSINESS_ID,
        is_active=None,
    )
    staff_by_name: Dict[str, SalonStaffResponse] = {
        st.full_name.strip().lower(): st for st in existing_staff
    }

    staff_created: List[SalonStaffResponse] = []
    staff_existing: List[SalonStaffResponse] = []
    mappings_updated = 0
    hours_configured = 0

    for spec in SHREYANSH_DEMO_STAFF:
        full_name = str(spec["full_name"])
        key = full_name.strip().lower()
        target_service_ids: List[UUID] = [
            service_by_name[str(svc_name).strip().lower()].id
            for svc_name in spec["services"]  # type: ignore[attr-defined]
        ]

        if key in staff_by_name:
            member = staff_by_name[key]
            staff_existing.append(member)
            merged_ids = list(dict.fromkeys([*member.assigned_service_ids, *target_service_ids]))
            if set(merged_ids) != set(member.assigned_service_ids):
                await salon_service.assign_staff_services(
                    actor=actor,
                    organization_id=SHREYANSH_ORGANIZATION_ID,
                    business_id=SHREYANSH_BUSINESS_ID,
                    staff_id=member.id,
                    payload=SalonStaffServiceAssignmentRequest(service_ids=merged_ids),
                )
                mappings_updated += 1
        else:
            member = await salon_service.create_staff(
                actor=actor,
                organization_id=SHREYANSH_ORGANIZATION_ID,
                business_id=SHREYANSH_BUSINESS_ID,
                payload=SalonStaffCreateRequest(
                    full_name=full_name,
                    role_designation=str(spec["role_designation"]),
                    bio=str(spec["bio"]),
                    is_active=True,
                    assigned_service_ids=target_service_ids,
                ),
            )
            staff_created.append(member)
            staff_by_name[key] = member
            mappings_updated += 1

        current_hours = await salon_service.get_staff_working_hours(
            actor=actor,
            organization_id=SHREYANSH_ORGANIZATION_ID,
            business_id=SHREYANSH_BUSINESS_ID,
            staff_id=member.id,
        )
        if not current_hours:
            await salon_service.update_staff_working_hours(
                actor=actor,
                organization_id=SHREYANSH_ORGANIZATION_ID,
                business_id=SHREYANSH_BUSINESS_ID,
                staff_id=member.id,
                payload=SalonStaffWorkingHoursUpdateRequest(schedule=DEFAULT_DEMO_WEEKLY_SCHEDULE),
            )
            hours_configured += 1

    return {
        "services_created": len(services_created),
        "services_existing": len(services_existing),
        "staff_created": len(staff_created),
        "staff_existing": len(staff_existing),
        "mappings_updated": mappings_updated,
        "hours_configured": hours_configured,
    }


async def _main() -> None:
    settings = get_settings()
    salon_service = build_salon_workflow_service(settings=settings)
    actor = create_verified_internal_voice_actor(
        organization_id=SHREYANSH_ORGANIZATION_ID,
        business_id=SHREYANSH_BUSINESS_ID,
        industry=OrganizationIndustry.SALON,
        user_id=SHREYANSH_OWNER_USER_ID,
    )
    summary = await seed_shreyansh_salon_demo(salon_service, actor)
    print(f"[{datetime.now(timezone.utc).isoformat()}] Shreyansh salon seed summary: {summary}")


if __name__ == "__main__":
    asyncio.run(_main())
