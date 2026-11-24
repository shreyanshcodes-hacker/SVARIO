"""Idempotent temporary demo seed script for Riya Women salon catalogue.

Usage (requires backend Supabase credentials in apps/api/.env; never commit secrets):
    cd apps/api
    python -m scripts.seed_riya_salon_catalogue

Safety guarantees:
- Scoped strictly to Riya Women salon (`organization_id`, `business_id`).
- Checks existing services by case-insensitive trimmed name before inserting;
  running multiple times never creates duplicates and never overwrites manually
  created or unrelated services.
- Marks seeded rows with `SEED_MARKER` in `description` for safe later removal.
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
from app.modules.salons.schemas import SalonServiceCreateRequest, SalonServiceResponse
from app.modules.salons.service import SalonWorkflowService, build_salon_workflow_service

RIYA_ORGANIZATION_ID = UUID("8867eb36-95c3-4d87-b91f-a9e23f21c88b")
RIYA_BUSINESS_ID = UUID("1962bebf-c4b2-4a56-a79e-963f8bd7e334")
RIYA_OWNER_USER_ID = UUID("9c015524-1796-457d-b1c5-4528b43aa259")
SEED_MARKER = "[TEMP_DEMO_SEED:riya-salon-catalogue-v1]"

RIYA_DEMO_SERVICES: List[Dict[str, object]] = [
    {"name": "Basic Haircut", "category": "Hair", "price": 299.0, "currency": "INR", "duration_minutes": 30},
    {"name": "Haircut & Styling", "category": "Hair", "price": 499.0, "currency": "INR", "duration_minutes": 45},
    {"name": "Hair Spa", "category": "Hair", "price": 799.0, "currency": "INR", "duration_minutes": 60},
    {"name": "Hair Colour", "category": "Hair", "price": 1499.0, "currency": "INR", "duration_minutes": 120},
    {"name": "Basic Facial", "category": "Skin", "price": 699.0, "currency": "INR", "duration_minutes": 45},
    {"name": "Premium Facial", "category": "Skin", "price": 1299.0, "currency": "INR", "duration_minutes": 75},
    {"name": "Cleanup", "category": "Skin", "price": 399.0, "currency": "INR", "duration_minutes": 30},
    {"name": "Manicure", "category": "Nails", "price": 349.0, "currency": "INR", "duration_minutes": 30},
    {"name": "Pedicure", "category": "Nails", "price": 499.0, "currency": "INR", "duration_minutes": 45},
    {"name": "Bridal Makeup", "category": "Makeup", "price": 4999.0, "currency": "INR", "duration_minutes": 180},
    {"name": "Party Makeup", "category": "Makeup", "price": 1999.0, "currency": "INR", "duration_minutes": 90},
    {"name": "Beard Trim", "category": "Grooming", "price": 199.0, "currency": "INR", "duration_minutes": 20},
]


async def seed_riya_salon_services(
    salon_service: SalonWorkflowService,
    actor: AuthenticatedUser,
) -> Tuple[List[SalonServiceResponse], List[SalonServiceResponse]]:
    """Idempotently seed the 12 temporary services for Riya Women salon.

    Returns `(inserted_services, skipped_existing_services)`.
    """
    existing = await salon_service.list_services(
        actor=actor,
        organization_id=RIYA_ORGANIZATION_ID,
        business_id=RIYA_BUSINESS_ID,
        is_active=None,
    )
    existing_by_name = {svc.name.strip().lower(): svc for svc in existing}

    inserted: List[SalonServiceResponse] = []
    skipped: List[SalonServiceResponse] = []

    for spec in RIYA_DEMO_SERVICES:
        name = str(spec["name"])
        key = name.strip().lower()
        if key in existing_by_name:
            skipped.append(existing_by_name[key])
            continue

        payload = SalonServiceCreateRequest(
            name=name,
            description=SEED_MARKER,
            category=str(spec["category"]),
            price=float(spec["price"]),
            currency=str(spec["currency"]),
            duration_minutes=int(spec["duration_minutes"]),
            is_active=True,
        )
        created = await salon_service.create_service(
            actor=actor,
            organization_id=RIYA_ORGANIZATION_ID,
            business_id=RIYA_BUSINESS_ID,
            payload=payload,
        )
        inserted.append(created)

    return inserted, skipped


async def _main() -> None:
    settings = get_settings()
    salon_service = build_salon_workflow_service(settings=settings)
    actor = create_verified_internal_voice_actor(
        organization_id=RIYA_ORGANIZATION_ID,
        business_id=RIYA_BUSINESS_ID,
        industry=OrganizationIndustry.SALON,
        user_id=RIYA_OWNER_USER_ID,
    )
    inserted, skipped = await seed_riya_salon_services(salon_service, actor)
    print(
        f"[{datetime.now(timezone.utc).isoformat()}] Seed complete for Riya Women salon: "
        f"inserted={len(inserted)}, skipped_existing={len(skipped)}"
    )


if __name__ == "__main__":
    asyncio.run(_main())
