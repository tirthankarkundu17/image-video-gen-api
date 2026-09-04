import logging
from fastapi import APIRouter, Depends, status
from google import genai

from app.auth.dependencies import get_current_principal
from app.auth.gcp_auth import AuthenticatedPrincipal
from app.config import Settings, get_settings
from app.schemas.video import VideoGenerationRequest, VideoOperationResponse
from app.services.vertex_client import get_vertex_client
from app.services.video_service import generate_video, get_video_operation_status

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/videos", tags=["Video Generation"])


@router.post(
    "/generate",
    response_model=VideoOperationResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Generate videos using Vertex AI Veo",
    description=(
        "Initiates a video generation job using Google Vertex AI (e.g., Veo - veo-2.0-generate-001). "
        "Returns a long-running operation ID for polling, or optionally waits until completion if "
        "'wait_for_completion=true'. Protected by GCP Service Account authentication."
    ),
)
async def generate_video_endpoint(
    request: VideoGenerationRequest,
    principal: AuthenticatedPrincipal = Depends(get_current_principal),
    client: genai.Client = Depends(get_vertex_client),
    settings: Settings = Depends(get_settings),
) -> VideoOperationResponse:
    logger.info(
        "Video generation requested by caller=%s (auth_type=%s) for prompt: '%s'",
        principal.email or principal.identifier,
        principal.auth_type,
        request.prompt,
    )
    return await generate_video(request=request, client=client, settings=settings)


@router.get(
    "/operations/{operation_id:path}",
    response_model=VideoOperationResponse,
    summary="Poll status of a video generation operation",
    description=(
        "Retrieves the status, progress, and result (URI or base64 data) of an ongoing or completed "
        "Vertex AI video generation operation. Pass the full operation resource name."
    ),
)
def get_video_operation_endpoint(
    operation_id: str,
    principal: AuthenticatedPrincipal = Depends(get_current_principal),
    client: genai.Client = Depends(get_vertex_client),
) -> VideoOperationResponse:
    logger.debug(
        "Operation status check requested by caller=%s for operation: '%s'",
        principal.email or principal.identifier,
        operation_id,
    )
    return get_video_operation_status(operation_id=operation_id, client=client)
