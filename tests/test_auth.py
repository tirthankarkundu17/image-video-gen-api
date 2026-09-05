from unittest.mock import AsyncMock, MagicMock, patch
from app.auth.gcp_auth import AuthenticatedPrincipal
from app.config import Settings, get_settings
from app.main import app


def test_missing_auth_header_fails(client):
    response = client.post(
        "/api/v1/images/generate",
        json={"prompt": "A scenic sunset over ocean"},
    )
    assert response.status_code == 401
    assert "Missing Authorization header" in response.json()["detail"]


def test_invalid_bearer_format_fails(client):
    response = client.post(
        "/api/v1/images/generate",
        json={"prompt": "A scenic sunset over ocean"},
        headers={"Authorization": "Token 12345"},
    )
    assert response.status_code == 401
    assert "Invalid Authorization header format" in response.json()["detail"]


def test_invalid_api_key_fails(client):
    response = client.post(
        "/api/v1/images/generate",
        json={"prompt": "A scenic sunset over ocean"},
        headers={"X-API-Key": "wrong-key"},
    )
    assert response.status_code == 401
    assert "Invalid API Key" in response.json()["detail"]


def test_valid_api_key_succeeds(client, mock_vertex_client):
    # Mock Vertex client image response
    mock_img = MagicMock()
    mock_img.image.image_bytes = b"fake-bytes"
    mock_img.image.mime_type = "image/png"
    mock_vertex_client.models.generate_images.return_value = MagicMock(
        generated_images=[mock_img]
    )

    response = client.post(
        "/api/v1/images/generate",
        json={"prompt": "A scenic sunset over ocean"},
        headers={"X-API-Key": "test-secret-key"},
    )
    assert response.status_code == 200


@patch("app.auth.dependencies.verify_google_bearer_token", new_callable=AsyncMock)
def test_valid_service_account_bearer_token(mock_verify, client, mock_vertex_client):
    mock_verify.return_value = AuthenticatedPrincipal(
        identifier="12345",
        auth_type="gcp_service_account",
        email="authorized-sa@test-project-123.iam.gserviceaccount.com",
    )

    mock_img = MagicMock()
    mock_img.image.image_bytes = b"fake-bytes"
    mock_img.image.mime_type = "image/png"
    mock_vertex_client.models.generate_images.return_value = MagicMock(
        generated_images=[mock_img]
    )

    response = client.post(
        "/api/v1/images/generate",
        json={"prompt": "A scenic sunset over ocean"},
        headers={"Authorization": "Bearer google-token-abc"},
    )
    assert response.status_code == 200
    assert response.json()["total_images"] == 1


@patch("app.auth.dependencies.verify_google_bearer_token", new_callable=AsyncMock)
def test_unauthorized_service_account_rejected(mock_verify, client):
    mock_verify.side_effect = ValueError(
        "Service account 'unauthorized@project.iam.gserviceaccount.com' is not in the allowed callers list"
    )

    response = client.post(
        "/api/v1/images/generate",
        json={"prompt": "A scenic sunset over ocean"},
        headers={"Authorization": "Bearer google-token-abc"},
    )
    assert response.status_code == 403
    assert "not in the allowed callers list" in response.json()["detail"]


def test_auth_disabled_bypass(client, mock_vertex_client):
    disabled_settings = Settings(
        GCP_PROJECT_ID="test-project",
        AUTH_ENABLED=False,
        DEFAULT_IMAGE_MODEL="imagen-3.0-generate-002",
    )
    app.dependency_overrides[get_settings] = lambda: disabled_settings

    mock_img = MagicMock()
    mock_img.image.image_bytes = b"fake-bytes"
    mock_img.image.mime_type = "image/png"
    mock_vertex_client.models.generate_images.return_value = MagicMock(
        generated_images=[mock_img]
    )

    response = client.post(
        "/api/v1/images/generate",
        json={"prompt": "A scenic sunset over ocean"},
    )
    assert response.status_code == 200


@patch("google.oauth2.service_account.Credentials.from_service_account_info")
def test_get_vertex_credentials_from_info(mock_from_info):
    from app.auth.gcp_auth import get_vertex_credentials
    mock_from_info.return_value = MagicMock()

    settings = Settings(
        _env_file=None,
        GCP_PROJECT_ID="",
        GCP_SERVICE_ACCOUNT_INFO='{"type": "service_account", "project_id": "inline-proj"}',
    )
    creds, proj = get_vertex_credentials(settings)
    assert proj == "inline-proj"
    mock_from_info.assert_called_once()


@patch("google.auth.default")
def test_get_vertex_credentials_from_adc(mock_default):
    from app.auth.gcp_auth import get_vertex_credentials
    mock_default.return_value = (MagicMock(), "adc-proj")

    settings = Settings(_env_file=None, GCP_PROJECT_ID="", GCP_SERVICE_ACCOUNT_FILE="")
    creds, proj = get_vertex_credentials(settings)
    assert proj == "adc-proj"
    mock_default.assert_called_once()

