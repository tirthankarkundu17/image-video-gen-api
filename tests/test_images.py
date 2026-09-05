import base64
from unittest.mock import MagicMock
from google.genai import errors as genai_errors


def test_generate_image_success(client, auth_headers, mock_vertex_client):
    fake_png_bytes = b"\x89PNG\r\n\x1a\nfakeimagebytes"
    mock_img = MagicMock()
    mock_img.image.image_bytes = fake_png_bytes
    mock_img.image.mime_type = "image/png"
    mock_img.image.gcs_uri = None

    mock_vertex_client.models.generate_images.return_value = MagicMock(
        generated_images=[mock_img]
    )

    payload = {
        "prompt": "Cyberpunk city street at night with neon signs",
        "aspect_ratio": "16:9",
        "number_of_images": 1,
        "output_mime_type": "image/png",
    }

    response = client.post(
        "/api/v1/images/generate",
        json=payload,
        headers=auth_headers,
    )

    assert response.status_code == 200
    data = response.json()
    assert data["model"] == "imagen-3.0-generate-002"
    assert data["prompt"] == payload["prompt"]
    assert data["total_images"] == 1
    assert len(data["images"]) == 1

    first_image = data["images"][0]
    assert first_image["index"] == 1
    assert first_image["mime_type"] == "image/png"
    decoded = base64.b64decode(first_image["base64_data"])
    assert decoded == fake_png_bytes


def test_generate_image_validation_failure(client, auth_headers):
    # Missing prompt
    response = client.post(
        "/api/v1/images/generate",
        json={"prompt": ""},
        headers=auth_headers,
    )
    assert response.status_code == 422

    # Invalid aspect ratio
    response = client.post(
        "/api/v1/images/generate",
        json={"prompt": "valid prompt", "aspect_ratio": "invalid_ratio"},
        headers=auth_headers,
    )
    assert response.status_code == 422

    # Number of images exceeds limit
    response = client.post(
        "/api/v1/images/generate",
        json={"prompt": "valid prompt", "number_of_images": 10},
        headers=auth_headers,
    )
    assert response.status_code == 422


def test_generate_image_safety_filter_empty_response(client, auth_headers, mock_vertex_client):
    mock_vertex_client.models.generate_images.return_value = MagicMock(
        generated_images=[]
    )

    response = client.post(
        "/api/v1/images/generate",
        json={"prompt": "Something that triggers safety filters"},
        headers=auth_headers,
    )
    assert response.status_code == 502
    assert "Vertex AI returned no images" in response.json()["detail"]


def test_generate_image_vertex_api_error(client, auth_headers, mock_vertex_client):
    mock_vertex_client.models.generate_images.side_effect = genai_errors.APIError(
        code=400, response_json={"message": "Quota exceeded"}
    )

    response = client.post(
        "/api/v1/images/generate",
        json={"prompt": "A test prompt"},
        headers=auth_headers,
    )
    assert response.status_code == 502
    assert "Vertex AI API error" in response.json()["detail"]


def test_generate_image_with_gcs_upload_missing_bucket(client, auth_headers):
    response = client.post(
        "/api/v1/images/generate",
        json={
            "prompt": "Cyberpunk city street",
            "upload_to_gcs": True,
        },
        headers=auth_headers,
    )
    assert response.status_code == 400
    assert "no GCS bucket was configured" in response.json()["detail"]


def test_generate_image_with_gcs_upload_success(client, auth_headers, mock_vertex_client):
    from unittest.mock import patch

    fake_png_bytes = b"\x89PNG\r\n\x1a\nfakeimagebytes"
    mock_img = MagicMock()
    mock_img.image.image_bytes = fake_png_bytes
    mock_img.image.mime_type = "image/png"
    mock_vertex_client.models.generate_images.return_value = MagicMock(
        generated_images=[mock_img]
    )

    with patch("app.services.image_service.upload_image_bytes") as mock_upload:
        mock_upload.return_value = (
            "gs://my-bucket/generated-images/test_img.png",
            "https://storage.googleapis.com/my-bucket/generated-images/test_img.png",
        )

        response = client.post(
            "/api/v1/images/generate",
            json={
                "prompt": "Cyberpunk street",
                "upload_to_gcs": True,
                "gcs_bucket": "my-bucket",
                "include_base64": False,
            },
            headers=auth_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert len(data["images"]) == 1
        img = data["images"][0]
        assert img["gcs_uri"] == "gs://my-bucket/generated-images/test_img.png"
        assert img["gcs_url"] == "https://storage.googleapis.com/my-bucket/generated-images/test_img.png"
        assert img["base64_data"] is None
        mock_upload.assert_called_once()


def test_generate_image_gemini_model_success(client, auth_headers, mock_vertex_client):
    fake_jpeg_bytes = b"\xff\xd8\xff\xe0fakejpegbytes"
    mock_part = MagicMock()
    mock_part.inline_data.data = fake_jpeg_bytes
    mock_part.inline_data.mime_type = "image/jpeg"

    mock_candidate = MagicMock()
    mock_candidate.content.parts = [mock_part]

    mock_vertex_client.models.generate_content.return_value = MagicMock(
        candidates=[mock_candidate]
    )

    response = client.post(
        "/api/v1/images/generate",
        json={
            "prompt": "A cute cat on a skateboard",
            "model": "gemini-3.1-flash-lite-image",
        },
        headers=auth_headers,
    )

    assert response.status_code == 200
    data = response.json()
    assert data["model"] == "gemini-3.1-flash-lite-image"
    assert len(data["images"]) == 1
    assert data["images"][0]["mime_type"] == "image/jpeg"
    assert base64.b64decode(data["images"][0]["base64_data"]) == fake_jpeg_bytes

