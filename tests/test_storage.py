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
