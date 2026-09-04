from datetime import datetime, timezone
import logging

from fastapi import APIRouter, Depends

from app.config import Settings, get_settings
from app.schemas.common import HealthResponse, ReadinessResponse
from app.services.vertex_client import get_vertex_client

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Health & Monitoring"])


@router.get(
    "/healthz",
    response_model=HealthResponse,
    summary="Liveness probe",
    description="Returns 200 OK if the application service is running.",
)
def health_check() -> HealthResponse:
    return HealthResponse(
        status="healthy",
        version="0.1.0",
        timestamp=datetime.now(timezone.utc).isoformat(),
    )


@router.get(
    "/readyz",
    response_model=ReadinessResponse,
    summary="Readiness probe",
    description="Verifies GCP configuration and Vertex AI client connectivity readiness.",
)
def readiness_check(settings: Settings = Depends(get_settings)) -> ReadinessResponse:
    client_ready = False
    details = {}

    try:
        client = get_vertex_client(settings)
        client_ready = client is not None
    except Exception as e:
        logger.warning("Vertex client initialization test in readiness check: %s", e)
        details["initialization_warning"] = str(e)

    status_str = "ready" if (client_ready and settings.GCP_PROJECT_ID) else "degraded"

    return ReadinessResponse(
        status=status_str,
        gcp_project_id=settings.GCP_PROJECT_ID,
        gcp_location=settings.GCP_LOCATION,
        auth_enabled=settings.AUTH_ENABLED,
        vertex_client_ready=client_ready,
        details=details if details else None,
    )
