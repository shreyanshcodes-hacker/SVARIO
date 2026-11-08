"""Tests for Stage 1 Multi-Tenant Organization & Membership RBAC endpoints."""

from datetime import datetime, timedelta, timezone
from typing import Any, Dict
from uuid import UUID, uuid4
import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import ec
from fastapi.testclient import TestClient
from app.core.auth import SupabaseJWTVerifier, get_jwt_verifier
from app.core.config import Settings
from app.main import create_app
from app.modules.organizations.repository import InMemoryOrganizationRepository
from app.modules.organizations.service import (
    OrganizationService,
    get_organization_service,
)

TEST_ISSUER = "https://test-project.supabase.co/auth/v1"
TEST_AUDIENCE = "authenticated"
TEST_KID = "svario-org-test-key"


@pytest.fixture
def org_test_env() -> tuple[TestClient, ec.EllipticCurvePrivateKey]:
    """Provide a fresh TestClient with isolated InMemoryOrganizationRepository and ES256 keys."""
    private_key = ec.generate_private_key(ec.SECP256R1())
    public_key = private_key.public_key()

    settings = Settings(
        SUPABASE_URL="https://test-project.supabase.co",
        SUPABASE_JWT_ISSUER=TEST_ISSUER,
        SUPABASE_JWT_AUDIENCE=TEST_AUDIENCE,
        SUPABASE_JWT_ALGORITHMS="ES256",
    )

    verifier = SupabaseJWTVerifier(
        settings=settings,
        key_resolver=lambda _tok, _hdr: public_key,
    )
    repo = InMemoryOrganizationRepository()
    service = OrganizationService(repository=repo)

    app = create_app()
    app.dependency_overrides[get_jwt_verifier] = lambda: verifier
    app.dependency_overrides[get_organization_service] = lambda: service

    return TestClient(app), private_key


def issue_token(
    private_key: ec.EllipticCurvePrivateKey,
    user_id: UUID,
    email: str = "user@svario.ai",
    full_name: str = "Test User",
) -> str:
    """Issue a signed ES256 Bearer token for `user_id`."""
    now = datetime.now(timezone.utc)
    payload: Dict[str, Any] = {
        "sub": str(user_id),
        "email": email,
        "role": "authenticated",
        "iss": TEST_ISSUER,
        "aud": TEST_AUDIENCE,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(minutes=20)).timestamp()),
        "user_metadata": {"full_name": full_name, "email_verified": True},
    }
    return jwt.encode(
        payload,
        private_key,
        algorithm="ES256",
        headers={"kid": TEST_KID, "typ": "JWT"},
    )


def test_authenticated_user_creates_organization_and_becomes_owner(
    org_test_env: tuple[TestClient, ec.EllipticCurvePrivateKey],
) -> None:
    """Creator of an organization must become 'owner' and see it in their organization list."""
    client, key = org_test_env
    owner_id = uuid4()
    token = issue_token(key, owner_id, email="owner@lumiere-salon.com", full_name="Maya Kapoor")

    create_resp = client.post(
        "/api/v1/organizations",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "name": "Lumiere Luxe Salon",
            "industry": "salon",
            "timezone": "Asia/Kolkata",
        },
    )
    assert create_resp.status_code == 201
    created = create_resp.json()
    assert created["name"] == "Lumiere Luxe Salon"
    assert created["industry"] == "salon"
    assert created["membership_role"] == "owner"
    org_id = created["id"]

    # Member can list their organizations
    list_resp = client.get(
        "/api/v1/organizations",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert list_resp.status_code == 200
    orgs = list_resp.json()
    assert len(orgs) == 1
    assert orgs[0]["id"] == org_id
    assert orgs[0]["membership_role"] == "owner"

    # Member can read organization detail
    detail_resp = client.get(
        f"/api/v1/organizations/{org_id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert detail_resp.status_code == 200
    detail = detail_resp.json()
    assert detail["id"] == org_id
    assert detail["membership_role"] == "owner"
    assert detail["member_count"] == 1


def test_non_member_cannot_read_or_list_members_of_another_organization(
    org_test_env: tuple[TestClient, ec.EllipticCurvePrivateKey],
) -> None:
    """Users outside an organization must receive HTTP 403 when reading it or its members."""
    client, key = org_test_env
    user_a = uuid4()
    user_b = uuid4()
    token_a = issue_token(key, user_a, email="owner@apex-clinic.com")
    token_b = issue_token(key, user_b, email="outsider@other-org.com")

    create_resp = client.post(
        "/api/v1/organizations",
        headers={"Authorization": f"Bearer {token_a}"},
        json={"name": "Apex Dental Clinic", "industry": "clinic"},
    )
    assert create_resp.status_code == 201
    org_id = create_resp.json()["id"]

    # User B lists their organizations -> empty
    list_b = client.get(
        "/api/v1/organizations",
        headers={"Authorization": f"Bearer {token_b}"},
    )
    assert list_b.status_code == 200
    assert list_b.json() == []

    # User B tries to read User A's organization by ID -> 403 Forbidden
    get_b = client.get(
        f"/api/v1/organizations/{org_id}",
        headers={"Authorization": f"Bearer {token_b}"},
    )
    assert get_b.status_code == 403

    # User B tries to list members of User A's organization -> 403 Forbidden
    members_b = client.get(
        f"/api/v1/organizations/{org_id}/members",
        headers={"Authorization": f"Bearer {token_b}"},
    )
    assert members_b.status_code == 403


def test_staff_cannot_perform_owner_or_admin_member_management(
    org_test_env: tuple[TestClient, ec.EllipticCurvePrivateKey],
) -> None:
    """Staff members can read the organization but cannot add members or escalate roles."""
    client, key = org_test_env
    owner_id = uuid4()
    staff_id = uuid4()
    third_user_id = uuid4()

    owner_token = issue_token(key, owner_id, email="owner@metro-hospital.org")
    staff_token = issue_token(key, staff_id, email="staff@metro-hospital.org")

    org_resp = client.post(
        "/api/v1/organizations",
        headers={"Authorization": f"Bearer {owner_token}"},
        json={"name": "Metro City Hospital", "industry": "hospital"},
    )
    assert org_resp.status_code == 201
    org_id = org_resp.json()["id"]

    # Owner adds staff_id with role 'staff'
    add_staff_resp = client.post(
        f"/api/v1/organizations/{org_id}/members",
        headers={"Authorization": f"Bearer {owner_token}"},
        json={"user_id": str(staff_id), "role": "staff", "full_name": "Rohan Verma"},
    )
    assert add_staff_resp.status_code == 201
    assert add_staff_resp.json()["role"] == "staff"

    # Staff member CAN read the organization and member list
    staff_org_view = client.get(
        f"/api/v1/organizations/{org_id}",
        headers={"Authorization": f"Bearer {staff_token}"},
    )
    assert staff_org_view.status_code == 200
    assert staff_org_view.json()["membership_role"] == "staff"

    staff_members_view = client.get(
        f"/api/v1/organizations/{org_id}/members",
        headers={"Authorization": f"Bearer {staff_token}"},
    )
    assert staff_members_view.status_code == 200
    assert len(staff_members_view.json()) == 2

    # Staff member CANNOT add another member (403 Forbidden)
    staff_add_attempt = client.post(
        f"/api/v1/organizations/{org_id}/members",
        headers={"Authorization": f"Bearer {staff_token}"},
        json={"user_id": str(third_user_id), "role": "staff"},
    )
    assert staff_add_attempt.status_code == 403

    # Staff member CANNOT promote themselves to owner via POST /members (403 Forbidden)
    staff_escalate_attempt = client.post(
        f"/api/v1/organizations/{org_id}/members",
        headers={"Authorization": f"Bearer {staff_token}"},
        json={"user_id": str(staff_id), "role": "owner"},
    )
    assert staff_escalate_attempt.status_code == 403


def test_admin_can_add_staff_but_cannot_grant_owner_or_admin(
    org_test_env: tuple[TestClient, ec.EllipticCurvePrivateKey],
) -> None:
    """Admins can add staff members but cannot escalate anyone to admin or owner."""
    client, key = org_test_env
    owner_id = uuid4()
    admin_id = uuid4()
    new_staff_id = uuid4()
    rogue_owner_id = uuid4()

    owner_token = issue_token(key, owner_id)
    admin_token = issue_token(key, admin_id)

    org_id = client.post(
        "/api/v1/organizations",
        headers={"Authorization": f"Bearer {owner_token}"},
        json={"name": "Aura Skin Clinic", "industry": "clinic"},
    ).json()["id"]

    # Owner adds admin_id as 'admin'
    resp_admin = client.post(
        f"/api/v1/organizations/{org_id}/members",
        headers={"Authorization": f"Bearer {owner_token}"},
        json={"user_id": str(admin_id), "role": "admin"},
    )
    assert resp_admin.status_code == 201

    # Admin adds new_staff_id as 'staff' -> 201 Created
    resp_staff = client.post(
        f"/api/v1/organizations/{org_id}/members",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"user_id": str(new_staff_id), "role": "staff"},
    )
    assert resp_staff.status_code == 201

    # Admin attempts to add rogue_owner_id as 'owner' -> 403 Forbidden
    resp_escalate = client.post(
        f"/api/v1/organizations/{org_id}/members",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"user_id": str(rogue_owner_id), "role": "owner"},
    )
    assert resp_escalate.status_code == 403


def test_invalid_industry_and_spoofed_fields_rejected(
    org_test_env: tuple[TestClient, ec.EllipticCurvePrivateKey],
) -> None:
    """Invalid industry or spoofed user_id in request body must be rejected with HTTP 422."""
    client, key = org_test_env
    user_id = uuid4()
    token = issue_token(key, user_id)

    # Invalid industry
    invalid_ind_resp = client.post(
        "/api/v1/organizations",
        headers={"Authorization": f"Bearer {token}"},
        json={"name": "Invalid Industry Org", "industry": "restaurant"},
    )
    assert invalid_ind_resp.status_code == 422

    # Spoofed user_id / role in organization creation body
    spoof_resp = client.post(
        "/api/v1/organizations",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "name": "Spoof Attempt Org",
            "industry": "salon",
            "user_id": str(uuid4()),
            "role": "owner",
        },
    )
    assert spoof_resp.status_code == 422
