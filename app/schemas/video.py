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
        description="Video duration in seconds (e.g. 5, 6, or 8 depending on model capabilities)",
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
        examples=["veo-2.0-generate-001"],
    )
    wait_for_completion: bool = Field(
        default=False,
        description="If true, server polls until video completes (subject to timeout); if false, returns operation ID immediately",
    )


class VideoOperationResponse(BaseModel):
    operation_id: str = Field(..., description="Unique operation identifier for tracking progress")
    status: VideoStatusLiteral = Field(..., description="Current status of the video generation job")
    model: Optional[str] = Field(default=None, description="Model used for generation")
    prompt: Optional[str] = Field(default=None, description="Original generation prompt")
    video_uri: Optional[str] = Field(
        default=None, description="Google Cloud Storage URI or external URL to the video file"
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
