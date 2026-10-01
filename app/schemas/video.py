from typing import Literal, Optional
from pydantic import BaseModel, Field


VideoAspectRatioLiteral = Literal["16:9", "9:16"]
VideoStatusLiteral = Literal["PENDING", "RUNNING", "COMPLETED", "FAILED"]
VideoPersonGenLiteral = Literal["dont_allow", "allow_adult", "allow_all"]


class VideoGenerationRequest(BaseModel):
    prompt: str = Field(
        ...,
        min_length=1,
        max_length=2000,
        description="Text description of the video to generate",
        examples=["A cinematic sweeping aerial shot of snow-capped mountains at sunrise, 4k resolution"],
    )
    aspect_ratio: Optional[VideoAspectRatioLiteral] = Field(
        default="16:9",
        description="Aspect ratio of the generated video",
    )
    duration_seconds: Optional[int] = Field(
        default=None,
        ge=3,
        le=10,
        description="Video duration in seconds (e.g. 4, 6, or 8 depending on model capabilities)",
    )
    fps: Optional[int] = Field(
        default=None,
        ge=24,
        le=60,
        description="Target frames per second (e.g. 24)",
    )
    person_generation: Optional[VideoPersonGenLiteral] = Field(
        default=None,
        description="Policy for generating people",
    )
    model: Optional[str] = Field(
        default=None,
        description="Vertex AI model identifier (defaults to configured DEFAULT_VIDEO_MODEL)",
        examples=["veo-3.1-generate-001"],
    )
    wait_for_completion: bool = Field(
        default=False,
        description="If true, server polls until video completes (subject to timeout); if false, returns operation ID immediately",
    )
    upload_to_gcs: bool = Field(
        default=False,
        description="Optional toggle to automatically upload/save generated video to Google Cloud Storage (GCS)",
    )
    gcs_bucket: Optional[str] = Field(
        default=None,
        description="Google Cloud Storage bucket name (overrides configured GCS_VIDEO_BUCKET or GCS_IMAGE_BUCKET)",
    )
    gcs_path_prefix: Optional[str] = Field(
        default=None,
        description="Optional folder/prefix path inside bucket (defaults to 'generated-videos')",
    )
    output_gcs_uri: Optional[str] = Field(
        default=None,
        description="Explicit Google Cloud Storage URI destination (e.g. gs://bucket-name/folder/)",
    )
    include_base64: bool = Field(
        default=True,
        description="Whether to include video_base64 in response (can be set to false when upload_to_gcs=true to save bandwidth)",
    )


class VideoOperationResponse(BaseModel):
    operation_id: str = Field(..., description="Unique operation identifier for tracking progress")
    status: VideoStatusLiteral = Field(..., description="Current status of the video generation job")
    model: Optional[str] = Field(default=None, description="Model used for generation")
    prompt: Optional[str] = Field(default=None, description="Original generation prompt")
    video_uri: Optional[str] = Field(
        default=None, description="Google Cloud Storage URI or external URL to the video file"
    )
    video_url: Optional[str] = Field(
        default=None,
        description="Presigned downloadable URL to the video file in Cloud Storage (valid for 30 minutes)",
    )
    gcs_url: Optional[str] = Field(
        default=None,
        description="Alias for video_url (presigned Cloud Storage download URL valid for 30 minutes)",
    )
    video_base64: Optional[str] = Field(
        default=None, description="Base64-encoded video data if downloaded inline"
    )
    mime_type: Optional[str] = Field(default="video/mp4", description="Video MIME type")
    error_message: Optional[str] = Field(
        default=None, description="Error message if the generation failed"
    )
    created_at: str = Field(..., description="Timestamp when generation started")
    updated_at: Optional[str] = Field(
        default=None, description="Timestamp of the latest status check"
    )
