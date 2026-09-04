import logging
from typing import Optional, Tuple

from fastapi import HTTPException, status
from google.cloud import storage
from google.cloud.exceptions import GoogleCloudError

from app.auth.gcp_auth import get_vertex_credentials
from app.config import Settings, get_settings

logger = logging.getLogger(__name__)

_cached_storage_client: Optional[storage.Client] = None


def create_storage_client(settings: Optional[Settings] = None) -> storage.Client:
    """
    Creates a Google Cloud Storage client using configured GCP credentials.
    """
    settings = settings or get_settings()
    credentials, project_id = get_vertex_credentials(settings)

    client_kwargs = {}
    effective_project = project_id or settings.GCP_PROJECT_ID
    if effective_project:
        client_kwargs["project"] = effective_project
    if credentials is not None:
        client_kwargs["credentials"] = credentials

    logger.info(
        "Initializing GCS client: project=%s, has_credentials=%s",
        effective_project,
        credentials is not None,
    )
    return storage.Client(**client_kwargs)


def get_storage_client(settings: Optional[Settings] = None) -> storage.Client:
    """
    Returns the singleton or cached Google Cloud Storage client.
    """
    global _cached_storage_client
    if _cached_storage_client is None:
        _cached_storage_client = create_storage_client(settings)
    return _cached_storage_client


def reset_storage_client() -> None:
    """Resets the cached storage client (useful in tests)."""
    global _cached_storage_client
    _cached_storage_client = None


def upload_image_bytes(
    image_bytes: bytes,
    bucket_name: str,
    destination_blob_name: str,
    content_type: str = "image/png",
    storage_client: Optional[storage.Client] = None,
) -> Tuple[str, str]:
    """
    Uploads raw image bytes to a Google Cloud Storage bucket.

    Returns:
        Tuple of (gcs_uri, gcs_url) e.g.
        ("gs://bucket-name/folder/image.png", "https://storage.googleapis.com/bucket-name/folder/image.png")
    """
    client = storage_client or get_storage_client()

    try:
        bucket = client.bucket(bucket_name)
        blob = bucket.blob(destination_blob_name)
        blob.upload_from_string(image_bytes, content_type=content_type)
    except GoogleCloudError as gcs_err:
        logger.error(
            "Google Cloud Storage error uploading to gs://%s/%s: %s",
            bucket_name,
            destination_blob_name,
            gcs_err,
        )
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Google Cloud Storage upload failed: {str(gcs_err)}",
        )
    except Exception as exc:
        logger.error(
            "Unexpected error uploading to gs://%s/%s: %s",
            bucket_name,
            destination_blob_name,
            exc,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to upload image to Cloud Storage: {str(exc)}",
        )

    gcs_uri = f"gs://{bucket_name}/{destination_blob_name}"
    gcs_url = f"https://storage.googleapis.com/{bucket_name}/{destination_blob_name}"

    logger.info("Successfully uploaded image to %s", gcs_uri)
    return gcs_uri, gcs_url
