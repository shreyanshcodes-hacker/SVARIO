"""Tests for GET / and error handling."""

from fastapi.testclient import TestClient


def test_root_endpoint_returns_platform_foundation(client: TestClient) -> None:
    """Verify GET / returns platform identity, tagline, and target industries."""
    response = client.get("/")
    assert response.status_code == 200
    payload = response.json()
    assert payload["platform"] == "SVARIO"
    assert payload["tagline"] == "AI that speaks for your business."
    assert payload["service"] == "Svario API"
    assert payload["stage"] == 0
    assert payload["industries"] == ["salons", "clinics", "hospitals"]


def test_not_found_returns_json_error(client: TestClient) -> None:
    """Verify unknown routes return a 404 JSON response."""
    response = client.get("/non-existent-route")
    assert response.status_code == 404
    payload = response.json()
    assert "detail" in payload or "error" in payload
