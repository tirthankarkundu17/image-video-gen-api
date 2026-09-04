from datetime import datetime, timezone
import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from app.auth.dependencies import get_current_principal
from app.auth.gcp_auth import AuthenticatedPrincipal
from app.config import Settings, get_settings
from app.services.storage_service import upload_image_bytes

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/storage", tags=["Storage Diagnostics"])


class TestUploadRequest(BaseModel):
    bucket: Optional[str] = Field(
        default=None,
        description="GCS bucket name to test (defaults to configured GCS_IMAGE_BUCKET)",
    )
    path_prefix: Optional[str] = Field(
        default="test-uploads",
        description="Folder prefix within the bucket for test files",
    )


class TestUploadResponse(BaseModel):
    status: str
    bucket: str
    blob_name: str
    gcs_uri: str
    gcs_url: str
    uploaded_at: str
    message: str


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
