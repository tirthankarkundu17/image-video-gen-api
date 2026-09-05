import logging
from typing import Optional

from fastapi import Depends
from google import genai
from google.genai import errors as genai_errors

from app.auth.gcp_auth import get_vertex_credentials
from app.config import Settings, get_settings

logger = logging.getLogger(__name__)

_cached_client: Optional[genai.Client] = None
_cached_project_id: Optional[str] = None


def create_vertex_client(settings: Optional[Settings] = None) -> genai.Client:
    """
    Creates a new Google Gen AI client configured for Vertex AI with Service Account credentials.
    """
    settings = settings or get_settings()

    credentials, project_id = get_vertex_credentials(settings)

    if not project_id and not settings.GCP_PROJECT_ID:
        logger.warning(
            "GCP_PROJECT_ID is not configured and could not be inferred from credentials. "
            "Vertex AI API calls will require a valid project ID."
        )

    client_kwargs = {
        "vertexai": True,
        "project": project_id or settings.GCP_PROJECT_ID,
        "location": settings.GCP_LOCATION,
    }

    if credentials is not None:
        client_kwargs["credentials"] = credentials

    logger.info(
        "Initializing Vertex AI client: project=%s, location=%s, has_credentials=%s",
        client_kwargs["project"],
        client_kwargs["location"],
        credentials is not None,
    )

    try:
        return genai.Client(**client_kwargs)
    except Exception as e:
        logger.error("Failed to initialize Vertex AI client: %s", e)
        raise


def get_vertex_client(settings: Settings = Depends(get_settings)) -> genai.Client:
    """
    Returns the singleton Vertex AI GenAI Client.
    """
    global _cached_client
    if _cached_client is None:
        _cached_client = create_vertex_client(settings)
    return _cached_client


def reset_vertex_client() -> None:
    """Resets the cached client (useful in tests or when settings reload)."""
    global _cached_client
    _cached_client = None
