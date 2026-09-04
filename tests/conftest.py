from unittest.mock import MagicMock, patch
import pytest
from starlette.testclient import TestClient

from app.auth.gcp_auth import AuthenticatedPrincipal
from app.config import Settings, get_settings
from app.main import app
from app.services.vertex_client import get_vertex_client


@pytest.fixture
def mock_settings():
    return Settings(
        GCP_PROJECT_ID="test-project-123",
        GCP_LOCATION="us-central1",
        AUTH_ENABLED=True,
        ALLOWED_SERVICE_ACCOUNTS="authorized-sa@test-project-123.iam.gserviceaccount.com",
        API_KEY="test-secret-key",
        DEFAULT_IMAGE_MODEL="imagen-3.0-generate-002",
        DEFAULT_VIDEO_MODEL="veo-2.0-generate-001",
        VIDEO_POLL_INTERVAL_SECONDS=0.01,
        VIDEO_POLL_TIMEOUT_SECONDS=1.0,
    )


@pytest.fixture
def mock_vertex_client():
    client = MagicMock()
    # Mock models
    client.models = MagicMock()
    # Mock operations
    client.operations = MagicMock()
    return client


@pytest.fixture
def client(mock_settings, mock_vertex_client):
    app.dependency_overrides[get_settings] = lambda: mock_settings
    app.dependency_overrides[get_vertex_client] = lambda: mock_vertex_client

    with TestClient(app) as test_client:
        yield test_client

    app.dependency_overrides.clear()


@pytest.fixture
def auth_headers():
    return {"X-API-Key": "test-secret-key"}
