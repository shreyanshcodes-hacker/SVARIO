"""Tests for GET /health endpoint."""

from fastapi.testclient import TestClient


def test_health_endpoint_returns_expected_contract(client: TestClient) -> None:
    """Verify GET /health returns status, service='Svario API', and stage=0."""
    response = client.get("/health")
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert payload["service"] == "Svario API"
    assert payload["stage"] == 0
