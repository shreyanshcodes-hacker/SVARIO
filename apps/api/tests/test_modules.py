"""Tests for multi-industry architectural boundaries (Stage 0)."""

from fastapi.testclient import TestClient
from app.modules.registry import (
    get_industry_descriptors,
    get_registered_industry_modules,
    get_shared_subsystem_boundaries,
)
from app.modules.shared.contracts import IndustryDomain, IndustryModuleContract


def test_all_industry_modules_implement_contract() -> None:
    """Ensure Salons, Clinics, and Hospitals modules satisfy IndustryModuleContract."""
    modules = get_registered_industry_modules()
    assert len(modules) == 3
    for mod in modules:
        assert isinstance(mod, IndustryModuleContract)


def test_industry_descriptors_cover_three_target_industries() -> None:
    """Ensure descriptors exist for Salons, Clinics, and Hospitals."""
    descriptors = get_industry_descriptors()
    domains = [d.domain for d in descriptors]
    assert domains == [
        IndustryDomain.SALONS,
        IndustryDomain.CLINICS,
        IndustryDomain.HOSPITALS,
    ]
    for descriptor in descriptors:
        assert set(descriptor.shared_dependencies) == {
            "voice",
            "ai",
            "scheduling",
            "notifications",
        }


def test_shared_subsystem_boundaries_defined() -> None:
    """Ensure shared Voice, AI, Scheduling, and Notifications boundaries exist."""
    boundaries = get_shared_subsystem_boundaries()
    ids = [b.subsystem_id for b in boundaries]
    assert ids == ["voice", "ai", "scheduling", "notifications"]


def test_architecture_endpoint(client: TestClient) -> None:
    """Verify GET /architecture returns Stage 0 module and subsystem boundaries."""
    response = client.get("/architecture")
    assert response.status_code == 200
    data = response.json()
    assert data["stage"] == 0
    assert len(data["industry_modules"]) == 3
    assert len(data["shared_subsystems"]) == 4
