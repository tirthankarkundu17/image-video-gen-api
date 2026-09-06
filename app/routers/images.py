import logging
from typing import Optional
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from google import genai

from app.auth.dependencies import get_current_principal
from app.auth.gcp_auth import AuthenticatedPrincipal
from app.config import Settings, get_settings
from app.schemas.image import (
    AspectRatioLiteral,
    ImageGenerationRequest,
    ImageGenerationResponse,
    OutputMimeTypeLiteral,
    PersonGenerationLiteral,
    SafetyFilterLiteral,
)
from app.services.image_service import generate_images, generate_images_with_image_input
from app.services.vertex_client import get_vertex_client

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/images", tags=["Image Generation"])


@router.post(
    "/generate",
    response_model=ImageGenerationResponse,
    status_code=status.HTTP_200_OK,
    summary="Generate images using Vertex AI Imagen",
    description=(
        "Generates one or more images based on a text prompt using Google Vertex AI "
        "(e.g., Imagen 3 - imagen-3.0-generate-002). Protected by GCP Service Account authentication."
    ),
)
def generate_images_endpoint(
    request: ImageGenerationRequest,
    principal: AuthenticatedPrincipal = Depends(get_current_principal),
    client: genai.Client = Depends(get_vertex_client),
    settings: Settings = Depends(get_settings),
) -> ImageGenerationResponse:
    logger.info(
        "Image generation requested by caller=%s (auth_type=%s) for prompt: '%s'",
        principal.email or principal.identifier,
        principal.auth_type,
        request.prompt,
    )
    return generate_images(request=request, client=client, settings=settings)


@router.post(
    "/generate-from-image",
    response_model=ImageGenerationResponse,
    status_code=status.HTTP_200_OK,
    summary="Generate images conditioned on an input image and prompt",
    description=(
        "Accepts a multipart/form-data upload containing an input image file and a text prompt. "
        "Generates images conditioned on the provided image using Google Vertex AI "
        "(e.g., Gemini multimodal or Imagen 3 editing models). Protected by GCP Service Account authentication."
    ),
)
async def generate_images_from_image_endpoint(
    image: UploadFile = File(
        ...,
        description="Input reference/conditioning image file (PNG, JPEG, WEBP, GIF)",
    ),
    prompt: str = Form(
        ...,
        min_length=1,
        max_length=2000,
        description="Text description or instruction to generate/edit the image",
        examples=["Transform this photo into an oil painting in the style of Van Gogh"],
    ),
    model: Optional[str] = Form(
        default=None,
        description="Vertex AI model identifier (defaults to gemini-2.0-flash)",
    ),
    negative_prompt: Optional[str] = Form(
        default=None,
        max_length=1000,
        description="Text describing elements to avoid in the generated image",
    ),
    aspect_ratio: Optional[AspectRatioLiteral] = Form(
        default="1:1",
        description="Aspect ratio of the generated image",
    ),
    number_of_images: int = Form(
        default=1,
        ge=1,
        le=4,
        description="Number of images to generate (1 to 4)",
    ),
    output_mime_type: OutputMimeTypeLiteral = Form(
        default="image/png",
        description="MIME type format for generated images",
    ),
    person_generation: Optional[PersonGenerationLiteral] = Form(
        default=None,
        description="Policy for generating people",
    ),
    safety_filter_level: Optional[SafetyFilterLiteral] = Form(
        default=None,
        description="Safety filter sensitivity level",
    ),
    upload_to_gcs: bool = Form(
        default=False,
        description="Optional toggle to upload generated images to Google Cloud Storage (GCS)",
    ),
    gcs_bucket: Optional[str] = Form(
        default=None,
        description="Google Cloud Storage bucket name",
    ),
    gcs_path_prefix: Optional[str] = Form(
        default=None,
        description="Optional folder/prefix path inside bucket",
    ),
    include_base64: bool = Form(
        default=True,
        description="Whether to include base64_data in response",
    ),
    principal: AuthenticatedPrincipal = Depends(get_current_principal),
    client: genai.Client = Depends(get_vertex_client),
    settings: Settings = Depends(get_settings),
) -> ImageGenerationResponse:
    allowed_mime_types = {"image/jpeg", "image/png", "image/webp", "image/gif"}
    content_type = (image.content_type or "").lower()
    if content_type not in allowed_mime_types:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported image type: '{content_type}'. Supported types: {sorted(list(allowed_mime_types))}",
        )

    image_bytes = await image.read()
    if not image_bytes:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Uploaded image file is empty.",
        )

    logger.info(
        "Image-conditioned generation requested by caller=%s (auth_type=%s) for prompt: '%s' (image_size=%d bytes, mime=%s)",
        principal.email or principal.identifier,
        principal.auth_type,
        prompt,
        len(image_bytes),
        content_type,
    )

    return generate_images_with_image_input(
        prompt=prompt,
        image_bytes=image_bytes,
        image_mime_type=content_type,
        client=client,
        settings=settings,
        model=model,
        negative_prompt=negative_prompt,
        aspect_ratio=aspect_ratio,
        number_of_images=number_of_images,
        output_mime_type=output_mime_type,
        person_generation=person_generation,
        safety_filter_level=safety_filter_level,
        upload_to_gcs=upload_to_gcs,
        gcs_bucket=gcs_bucket,
        gcs_path_prefix=gcs_path_prefix,
        include_base64=include_base64,
    )

