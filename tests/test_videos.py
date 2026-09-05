from unittest.mock import MagicMock
from google.genai import errors as genai_errors


def test_generate_video_async_initiation(client, auth_headers, mock_vertex_client):
    mock_op = MagicMock()
    mock_op.name = "projects/123/locations/us-central1/publishers/google/models/veo-2.0-generate-001/operations/op-987"
    mock_op.done = False
    mock_op.error = None

    mock_vertex_client.models.generate_videos.return_value = mock_op

    payload = {
        "prompt": "Drone shot flying over a lush green canyon with waterfalls",
        "aspect_ratio": "16:9",
        "duration_seconds": 5,
        "wait_for_completion": False,
    }

    response = client.post(
        "/api/v1/videos/generate",
        json=payload,
        headers=auth_headers,
    )

    assert response.status_code == 202
    data = response.json()
    assert data["operation_id"] == mock_op.name
    assert data["status"] == "RUNNING"
    assert data["prompt"] == payload["prompt"]


def test_generate_video_validation_failure(client, auth_headers):
    # Missing prompt
    response = client.post(
        "/api/v1/videos/generate",
        json={"prompt": ""},
        headers=auth_headers,
    )
    assert response.status_code == 422

    # Invalid aspect ratio
    response = client.post(
        "/api/v1/videos/generate",
        json={"prompt": "test prompt", "aspect_ratio": "4:3"},
        headers=auth_headers,
    )
    assert response.status_code == 422

    # Duration seconds out of bounds (> 10)
    response = client.post(
        "/api/v1/videos/generate",
        json={"prompt": "test prompt", "duration_seconds": 60},
        headers=auth_headers,
    )
    assert response.status_code == 422


def test_get_video_operation_status_running(client, auth_headers, mock_vertex_client):
    op_name = "projects/123/locations/us-central1/publishers/google/models/veo/operations/op-123"

    mock_op = MagicMock()
    mock_op.name = op_name
    mock_op.done = False
    mock_op.error = None

    mock_vertex_client.operations.get.return_value = mock_op

    response = client.get(
        f"/api/v1/videos/operations/{op_name}",
        headers=auth_headers,
    )

    assert response.status_code == 200
    data = response.json()
    assert data["operation_id"] == op_name
    assert data["status"] == "RUNNING"


def test_get_video_operation_status_completed(client, auth_headers, mock_vertex_client):
    op_name = "projects/123/locations/us-central1/publishers/google/models/veo/operations/op-123"

    mock_video = MagicMock()
    mock_video.video.uri = "gs://my-bucket/generated_videos/video1.mp4"
    mock_video.video.video_bytes = None
    mock_video.video.mime_type = "video/mp4"

    mock_op = MagicMock()
    mock_op.name = op_name
    mock_op.done = True
    mock_op.error = None
    mock_op.response.generated_videos = [mock_video]

    mock_vertex_client.operations.get.return_value = mock_op

    response = client.get(
        f"/api/v1/videos/operations/{op_name}",
        headers=auth_headers,
    )

    assert response.status_code == 200
    data = response.json()
    assert data["operation_id"] == op_name
    assert data["status"] == "COMPLETED"
    assert data["video_uri"] == "gs://my-bucket/generated_videos/video1.mp4"
    assert data["mime_type"] == "video/mp4"


def test_get_video_operation_status_failed(client, auth_headers, mock_vertex_client):
    op_name = "projects/123/locations/us-central1/publishers/google/models/veo/operations/op-123"

    mock_op = MagicMock()
    mock_op.name = op_name
    mock_op.done = True
    mock_op.error = "Generation failed due to prompt violation"

    mock_vertex_client.operations.get.return_value = mock_op

    response = client.get(
        f"/api/v1/videos/operations/{op_name}",
        headers=auth_headers,
    )

    assert response.status_code == 200
    data = response.json()
    assert data["operation_id"] == op_name
    assert data["status"] == "FAILED"
    assert "prompt violation" in data["error_message"]


def test_generate_video_synchronous_wait(client, auth_headers, mock_vertex_client):
    op_name = "projects/123/locations/us-central1/publishers/google/models/veo/operations/op-sync"

    mock_video = MagicMock()
    mock_video.video.uri = "gs://my-bucket/generated_videos/sync_video.mp4"
    mock_video.video.video_bytes = None
    mock_video.video.mime_type = "video/mp4"

    # Initially running, then finished on poll
    initial_op = MagicMock()
    initial_op.name = op_name
    initial_op.done = False

    finished_op = MagicMock()
    finished_op.name = op_name
    finished_op.done = True
    finished_op.error = None
    finished_op.response.generated_videos = [mock_video]

    mock_vertex_client.models.generate_videos.return_value = initial_op
    mock_vertex_client.operations.get.return_value = finished_op

    payload = {
        "prompt": "Hyperlapse of clouds over mountain peaks",
        "wait_for_completion": True,
    }

    response = client.post(
        "/api/v1/videos/generate",
        json=payload,
        headers=auth_headers,
    )

    assert response.status_code == 202
    data = response.json()
    assert data["operation_id"] == op_name
    assert data["status"] == "COMPLETED"
    assert data["video_uri"] == "gs://my-bucket/generated_videos/sync_video.mp4"
