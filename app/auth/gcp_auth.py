import json
import logging
import os
from typing import Any, Dict, Optional, Tuple

import httpx
import google.auth
from google.auth.transport import requests as google_requests
from google.oauth2 import id_token, service_account

from app.config import Settings

logger = logging.getLogger(__name__)

VERTEX_SCOPES = ["https://www.googleapis.com/auth/cloud-platform"]
GOOGLE_TOKENINFO_URL = "https://oauth2.googleapis.com/tokeninfo"


class AuthenticatedPrincipal:
    """Represents an authenticated caller (Service Account or API Key)."""

    def __init__(
        self,
        identifier: str,
        auth_type: str,
        email: Optional[str] = None,
        claims: Optional[Dict[str, Any]] = None,
    ):
        self.identifier = identifier
        self.auth_type = auth_type
        self.email = email
        self.claims = claims or {}

    def __repr__(self) -> str:
        return f"<AuthenticatedPrincipal type={self.auth_type} email={self.email} id={self.identifier}>"


def get_vertex_credentials(settings: Settings) -> Tuple[Optional[Any], Optional[str]]:
    """
    Load GCP credentials for Vertex AI client calls.

    Returns:
        Tuple of (credentials_object, project_id)
    """
    project_id = settings.GCP_PROJECT_ID

    # 1. Check inline service account JSON
    if settings.GCP_SERVICE_ACCOUNT_INFO:
        try:
            info = json.loads(settings.GCP_SERVICE_ACCOUNT_INFO)
            credentials = service_account.Credentials.from_service_account_info(
                info, scopes=VERTEX_SCOPES
            )
            if not project_id and "project_id" in info:
                project_id = info["project_id"]
            logger.info("Loaded Vertex AI credentials from GCP_SERVICE_ACCOUNT_INFO")
            return credentials, project_id
        except Exception as e:
            logger.error("Failed to parse GCP_SERVICE_ACCOUNT_INFO: %s", e)
            raise ValueError(f"Invalid GCP_SERVICE_ACCOUNT_INFO: {e}")

    # 2. Check service account file path
    sa_file = settings.GCP_SERVICE_ACCOUNT_FILE or settings.GOOGLE_APPLICATION_CREDENTIALS
    if sa_file:
        if not os.path.exists(sa_file):
            logger.warning("GCP Service Account file not found at: %s", sa_file)
        else:
            try:
                credentials = service_account.Credentials.from_service_account_file(
                    sa_file, scopes=VERTEX_SCOPES
                )
                if not project_id:
                    with open(sa_file, "r", encoding="utf-8") as f:
                        data = json.load(f)
                        project_id = data.get("project_id")
                logger.info("Loaded Vertex AI credentials from file: %s", sa_file)
                return credentials, project_id
            except Exception as e:
                logger.error("Failed to load credentials from file %s: %s", sa_file, e)
                raise ValueError(f"Failed to load service account file: {e}")

    # 3. Fall back to Application Default Credentials (ADC)
    try:
        credentials, adc_project = google.auth.default(scopes=VERTEX_SCOPES)
        if not project_id:
            project_id = adc_project
        logger.info("Loaded Vertex AI credentials from Application Default Credentials (ADC)")
        return credentials, project_id
    except Exception as e:
        logger.warning(
            "Could not load Application Default Credentials: %s. Using default client fallback.",
            e,
        )
        return None, project_id


async def verify_google_bearer_token(
    token: str, settings: Settings
) -> AuthenticatedPrincipal:
    """
    Validates a Google Bearer token (either Google ID Token or Google OAuth2 Access Token).

    Args:
        token: Raw Bearer token string.
        settings: Application settings.

    Returns:
        AuthenticatedPrincipal instance.

    Raises:
        ValueError: If token is invalid or caller is not authorized.
    """
    email: Optional[str] = None
    claims: Dict[str, Any] = {}

    # Attempt 1: Validate as Google OIDC ID Token
    try:
        request_adapter = google_requests.Request()
        # Note: audience check is omitted/None for generic service account tokens unless specified
        id_info = id_token.verify_oauth2_token(token, request_adapter)
        email = id_info.get("email")
        claims = id_info
        logger.debug("Successfully validated Google ID token for email: %s", email)
    except Exception as id_err:
        logger.debug("Not a valid Google ID token (%s), attempting OAuth2 access token check", id_err)

        # Attempt 2: Validate as Google OAuth2 Access Token via Google tokeninfo
        try:
            async with httpx.AsyncClient(timeout=10.0) as http_client:
                resp = await http_client.get(
                    GOOGLE_TOKENINFO_URL, params={"access_token": token}
                )
                if resp.status_code == 200:
                    token_info = resp.json()
                    email = token_info.get("email")
                    claims = token_info
                    logger.debug(
                        "Successfully validated Google access token for email: %s", email
                    )
                else:
                    raise ValueError(f"Token verification endpoint returned {resp.status_code}: {resp.text}")
        except Exception as tokeninfo_err:
            raise ValueError(f"Failed to verify Google token: {tokeninfo_err}") from tokeninfo_err

    if not email:
        raise ValueError("Google token is valid but does not contain an associated email address")

    # Check allowed service accounts list if configured
    allowed = settings.allowed_service_account_list
    if allowed and email.lower() not in allowed:
        raise ValueError(
            f"Service account '{email}' is not in the allowed callers list: {allowed}"
        )

    return AuthenticatedPrincipal(
        identifier=claims.get("sub", email),
        auth_type="gcp_service_account",
        email=email,
        claims=claims,
    )
