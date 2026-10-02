from typing import Optional
from pydantic import BaseModel, Field, field_validator


class SignUrlRequest(BaseModel):
    gcs_uri: str = Field(
        ...,
        description="Google Cloud Storage URI to sign (e.g. gs://bucket-name/folder/video.mp4)",
        examples=["gs://my-bucket/generated-videos/123.mp4"],
    )
    expiration_minutes: int = Field(
        default=60,
        ge=1,
        le=10080,
        description="Presigned URL expiration time in minutes (default 60, max 10080 [7 days])",
    )

    @field_validator("gcs_uri")
    @classmethod
    def validate_gcs_uri(cls, v: str) -> str:
        v = v.strip()
        if not v.startswith("gs://"):
            raise ValueError("gcs_uri must start with 'gs://'")
        path_without_scheme = v[5:]
        if "/" not in path_without_scheme:
            raise ValueError("gcs_uri must contain both bucket and object path (e.g. gs://bucket/object)")
        bucket_name, blob_name = path_without_scheme.split("/", 1)
        if not bucket_name or not blob_name:
            raise ValueError("gcs_uri must contain both bucket and object path (e.g. gs://bucket/object)")
        return v


class SignUrlResponse(BaseModel):
    url: str = Field(..., description="Presigned/signed GCS URL")
    expires_in: int = Field(..., description="Expiration time in seconds")


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
