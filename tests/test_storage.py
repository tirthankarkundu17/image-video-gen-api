from unittest.mock import patch
from fastapi import status


def test_storage_upload_missing_bucket(client, auth_headers):
    # client fixture uses mock_settings where GCS_IMAGE_BUCKET is None
    response = client.post(
        "/api/v1/storage/test-upload",
        json={"bucket": ""},
        headers=auth_headers,
    )
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "No GCS bucket specified" in response.json()["detail"]


def test_storage_upload_success(client, auth_headers):
    with patch("app.routers.storage.upload_image_bytes") as mock_upload:
        mock_upload.return_value = (
            "gs://test-bucket/test-uploads/ping_123.png",
            "https://storage.googleapis.com/test-bucket/test-uploads/ping_123.png",
        )

        response = client.post(
            "/api/v1/storage/test-upload",
            json={"bucket": "test-bucket", "path_prefix": "diagnostics"},
            headers=auth_headers,
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["status"] == "success"
        assert data["bucket"] == "test-bucket"
        assert data["gcs_uri"] == "gs://test-bucket/test-uploads/ping_123.png"
        assert "storage.googleapis.com" in data["gcs_url"]
        mock_upload.assert_called_once()


def test_sign_url_success(client, auth_headers):
    with patch("app.services.storage_service.generate_signed_url") as mock_sign:
        mock_sign.return_value = "https://storage.googleapis.com/my-bucket/generated-videos/123.mp4?X-Goog-Algorithm=GOOG4-RSA-SHA256&sig=abc"

        response = client.post(
            "/api/v1/storage/sign-url",
            json={
                "gcs_uri": "gs://my-bucket/generated-videos/123.mp4",
                "expiration_minutes": 45,
            },
            headers=auth_headers,
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["url"] == "https://storage.googleapis.com/my-bucket/generated-videos/123.mp4?X-Goog-Algorithm=GOOG4-RSA-SHA256&sig=abc"
        assert data["expires_in"] == 45 * 60
        mock_sign.assert_called_once_with(
            "gs://my-bucket/generated-videos/123.mp4",
            expiration_minutes=45,
            settings=mock_sign.call_args.kwargs.get("settings"),
        )


def test_sign_url_default_expiration(client, auth_headers):
    with patch("app.services.storage_service.generate_signed_url") as mock_sign:
        mock_sign.return_value = "https://storage.googleapis.com/my-bucket/generated-videos/default.mp4?signed"

        response = client.post(
            "/api/v1/storage/sign-url",
            json={"gcs_uri": "gs://my-bucket/generated-videos/default.mp4"},
            headers=auth_headers,
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["url"] == "https://storage.googleapis.com/my-bucket/generated-videos/default.mp4?signed"
        assert data["expires_in"] == 60 * 60


def test_sign_url_invalid_uri_scheme(client, auth_headers):
    response = client.post(
        "/api/v1/storage/sign-url",
        json={"gcs_uri": "https://storage.googleapis.com/my-bucket/123.mp4"},
        headers=auth_headers,
    )
    assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY


def test_sign_url_invalid_uri_no_object(client, auth_headers):
    response = client.post(
        "/api/v1/storage/sign-url",
        json={"gcs_uri": "gs://my-bucket"},
        headers=auth_headers,
    )
    assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY


def test_sign_url_unauthorized(client):
    response = client.post(
        "/api/v1/storage/sign-url",
        json={"gcs_uri": "gs://my-bucket/video.mp4"},
    )
    assert response.status_code == status.HTTP_401_UNAUTHORIZED


def test_sign_url_service_failure(client, auth_headers):
    with patch("app.services.storage_service.generate_signed_url") as mock_sign:
        mock_sign.return_value = None

        response = client.post(
            "/api/v1/storage/sign-url",
            json={"gcs_uri": "gs://my-bucket/video.mp4"},
            headers=auth_headers,
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "Invalid GCS URI" in response.json()["detail"]
