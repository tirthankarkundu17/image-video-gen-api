from datetime import datetime, timezone
import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from app.auth.dependencies import get_current_principal
from app.auth.gcp_auth import AuthenticatedPrincipal
from app.config import Settings, get_settings
from app.schemas.storage import (
    SignUrlRequest,
    SignUrlResponse,
    TestUploadRequest,
    TestUploadResponse,
)
from app.services import storage_service
from app.services.storage_service import upload_image_bytes

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/storage", tags=["Storage"])


@router.post(
    "/sign-url",
    response_model=SignUrlResponse,
    status_code=status.HTTP_200_OK,
    summary="Generate a presigned URL for a GCS URI",
    description=(
        "Generates a V4 signed URL for a given Google Cloud Storage URI (gs://bucket/object). "
        "Allows time-limited direct access to private GCS objects."
    ),
)
def sign_gcs_url(
    payload: SignUrlRequest,
    principal: AuthenticatedPrincipal = Depends(get_current_principal),
    settings: Settings = Depends(get_settings),
) -> SignUrlResponse:
    logger.info(
        "Presigned URL requested for uri=%s (expiration=%dm) by %s",
        payload.gcs_uri,
        payload.expiration_minutes,
        principal.email or principal.identifier,
    )

    signed_url = storage_service.generate_signed_url(
        payload.gcs_uri,
        expiration_minutes=payload.expiration_minutes,
        settings=settings,
    )
    if not signed_url:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid GCS URI '{payload.gcs_uri}'. Expected format: 'gs://<bucket-name>/<object-path>'.",
        )

    return SignUrlResponse(
        url=signed_url,
        expires_in=payload.expiration_minutes * 60,
    )


# 1x1 transparent PNG bytes for a valid lightweight test image
TINY_TEST_PNG_BYTES = (
    b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
    b"\x08\x06\x00\x00\x00\x1f\x15c4\x00\x00\x00\rIDATx\x9cc\xf8\xff\xbf"
    b"\x1e\x00\x05\xfe\x02\xfe\xdc\xccY\xe7\x00\x00\x00\x00IEND\xaeB`\x82"
)


@router.post(
    "/test-upload",
    response_model=TestUploadResponse,
    status_code=status.HTTP_200_OK,
    summary="Test GCS bucket upload connectivity",
    description=(
        "Uploads a minimal 1x1 test image to the specified or configured GCS bucket "
        "to verify permissions, bucket existence, and connectivity."
    ),
)
def test_storage_upload_endpoint(
    request: Optional[TestUploadRequest] = None,
    principal: AuthenticatedPrincipal = Depends(get_current_principal),
    settings: Settings = Depends(get_settings),
) -> TestUploadResponse:
    request = request or TestUploadRequest()
    target_bucket = request.bucket or settings.GCS_IMAGE_BUCKET

    if not target_bucket:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "No GCS bucket specified. Provide 'bucket' in the request body "
                "or configure 'GCS_IMAGE_BUCKET' in your .env file."
            ),
        )

    prefix = (request.path_prefix or "test-uploads").strip("/")
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    blob_name = f"{prefix}/ping_{timestamp}.png" if prefix else f"ping_{timestamp}.png"

    logger.info(
        "Testing storage upload to gs://%s/%s initiated by %s",
        target_bucket,
        blob_name,
        principal.email or principal.identifier,
    )

    gcs_uri, gcs_url = upload_image_bytes(
        image_bytes=TINY_TEST_PNG_BYTES,
        bucket_name=target_bucket,
        destination_blob_name=blob_name,
        content_type="image/png",
    )

    return TestUploadResponse(
        status="success",
        bucket=target_bucket,
        blob_name=blob_name,
        gcs_uri=gcs_uri,
        gcs_url=gcs_url,
        uploaded_at=datetime.now(timezone.utc).isoformat(),
        message=f"Successfully uploaded test image to {gcs_uri}",
    )
