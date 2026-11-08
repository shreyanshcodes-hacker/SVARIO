"""Shared pytest fixtures for Svario API tests."""

import pytest
from fastapi.testclient import TestClient
from app.main import create_app


@pytest.fixture
def client() -> TestClient:
    """Create a FastAPI TestClient instance."""
    app = create_app()
    return TestClient(app)
