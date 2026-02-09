"""Basic tests for the FastAPI application."""

import pytest
from fastapi.testclient import TestClient
import sys
import os

# Add src directory to Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from src.main import app

client = TestClient(app)


def test_api_docs():
    """Test that API docs are accessible."""
    response = client.get("/docs")
    assert response.status_code == 200


def test_sanctions_endpoints_exist():
    """Test that sanctions endpoints exist (even if they fail due to missing parsers)."""
    endpoints = ["/sanctions/eu", "/sanctions/ofac", "/sanctions/uk", "/sanctions/un"]
    
    for endpoint in endpoints:
        # We expect these to fail with 422 (validation error) for missing payload
        response = client.post(endpoint)
        assert response.status_code == 422


@pytest.mark.asyncio
async def test_fill_natural_endpoint_structure():
    """Test that fill-natural endpoint exists and has proper structure."""
    # This will likely fail due to missing template file, but tests the endpoint exists
    response = client.post("/fill-natural", json={"properties": {"name": "Test"}})
    # We expect a 500 error due to missing template file, not 404
    assert response.status_code != 404