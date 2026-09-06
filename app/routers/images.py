import json
import logging
import mimetypes
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

ALLOWED_IMAGE_MIME_TYPES = {"image/jpeg", "image/png", "image/webp", "image/gif"}


def _resolve_image_mime_type(
    content_type: Optional[str], filename: Optional[str], data: bytes
) -> Optional[str]:
    """
    Resolves image MIME type by checking the HTTP Content-Type header,
    falling back to filename extension, and finally inspecting magic bytes.
    """
    if content_type and content_type.lower() in ALLOWED_IMAGE_MIME_TYPES:
        return content_type.lower()

    if filename:
        guessed, _ = mimetypes.guess_type(filename)
        if guessed and guessed.lower() in ALLOWED_IMAGE_MIME_TYPES:
            return guessed.lower()

    if data.startswith(b"\x89PNG"):
        return "image/png"
    if data.startswith(b"\xff\xd8"):
        return "image/jpeg"
    if data.startswith(b"GIF8"):
        return "image/gif"
    if data.startswith(b"RIFF") and len(data) >= 12 and data[8:12] == b"WEBP":
        return "image/webp"

    return None


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
    prompt: Optional[str] = Form(
        default=None,
        max_length=2000,
        description="Text description or instruction to generate/edit the image (required if not passed inside request_data JSON)",
        examples=["Transform this photo into an oil painting in the style of Van Gogh"],
    ),
    request_data: Optional[str] = Form(
        default=None,
        description="Optional JSON string of generation parameters (Option 2: multipart with JSON payload)",
    ),
    model: Optional[str] = Form(
        default=None,
        description="Vertex AI model identifier (defaults to gemini-3.1-flash-lite-image)",
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
    parsed_json = {}
    if request_data:
        try:
            parsed_json = json.loads(request_data)
        except Exception as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid JSON string in 'request_data': {str(exc)}",
            )

    effective_prompt = prompt or parsed_json.get("prompt")
    if not effective_prompt or not effective_prompt.strip():
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="'prompt' is required, either as a direct form field or inside 'request_data' JSON.",
        )

    effective_model = model or parsed_json.get("model")
    effective_negative_prompt = negative_prompt or parsed_json.get("negative_prompt")
    effective_aspect_ratio = (
        parsed_json.get("aspect_ratio", aspect_ratio)
        if aspect_ratio == "1:1" and "aspect_ratio" in parsed_json
        else aspect_ratio
    )
    effective_number_of_images = parsed_json.get("number_of_images", number_of_images)
    effective_output_mime_type = parsed_json.get("output_mime_type", output_mime_type)
    effective_person_generation = person_generation or parsed_json.get("person_generation")
    effective_safety_filter_level = safety_filter_level or parsed_json.get("safety_filter_level")
    effective_upload_to_gcs = parsed_json.get("upload_to_gcs", upload_to_gcs)
    effective_gcs_bucket = gcs_bucket or parsed_json.get("gcs_bucket")
    effective_gcs_path_prefix = gcs_path_prefix or parsed_json.get("gcs_path_prefix")
    effective_include_base64 = parsed_json.get("include_base64", include_base64)

    image_bytes = await image.read()
    if not image_bytes:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Uploaded image file is empty.",
        )

    resolved_mime_type = _resolve_image_mime_type(image.content_type, image.filename, image_bytes)
    if not resolved_mime_type:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"Unsupported image type: '{image.content_type}'. "
                f"Could not infer a valid image format from filename or content. "
                f"Supported types: {sorted(list(ALLOWED_IMAGE_MIME_TYPES))}"
            ),
        )

    logger.info(
        "Image-conditioned generation requested by caller=%s (auth_type=%s) for prompt: '%s' (image_size=%d bytes, mime=%s)",
        principal.email or principal.identifier,
        principal.auth_type,
        effective_prompt,
        len(image_bytes),
        resolved_mime_type,
    )

    return generate_images_with_image_input(
        prompt=effective_prompt,
        image_bytes=image_bytes,
        image_mime_type=resolved_mime_type,
        client=client,
        settings=settings,
        model=effective_model,
        negative_prompt=effective_negative_prompt,
        aspect_ratio=effective_aspect_ratio,
        number_of_images=effective_number_of_images,
        output_mime_type=effective_output_mime_type,
        person_generation=effective_person_generation,
        safety_filter_level=effective_safety_filter_level,
        upload_to_gcs=effective_upload_to_gcs,
        gcs_bucket=effective_gcs_bucket,
        gcs_path_prefix=effective_gcs_path_prefix,
        include_base64=effective_include_base64,
    )

