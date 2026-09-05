import logging
from fastapi import APIRouter, Depends, status
from google import genai

from app.auth.dependencies import get_current_principal
from app.auth.gcp_auth import AuthenticatedPrincipal
from app.config import Settings, get_settings
from app.schemas.image import ImageGenerationRequest, ImageGenerationResponse
from app.services.image_service import generate_images
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
