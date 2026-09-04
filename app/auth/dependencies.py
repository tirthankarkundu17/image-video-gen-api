import logging
from typing import Optional

from fastapi import Depends, Header, HTTPException, status

from app.auth.gcp_auth import AuthenticatedPrincipal, verify_google_bearer_token
from app.config import Settings, get_settings

logger = logging.getLogger(__name__)


async def get_current_principal(
    authorization: Optional[str] = Header(default=None, alias="Authorization"),
    x_api_key: Optional[str] = Header(default=None, alias="X-API-Key"),
    settings: Settings = Depends(get_settings),
) -> AuthenticatedPrincipal:
    """
    FastAPI security dependency to authenticate callers using GCP Service Account tokens or API key.
    """
    # 1. If auth is disabled in settings (e.g. for local development or testing)
    if not settings.AUTH_ENABLED:
        return AuthenticatedPrincipal(
            identifier="dev-user",
            auth_type="auth_disabled",
            email="developer@localhost",
            claims={"role": "developer"},
        )

    # 2. Check X-API-Key if configured
    if settings.API_KEY and x_api_key:
        if x_api_key == settings.API_KEY:
            return AuthenticatedPrincipal(
                identifier="api-key-caller",
                auth_type="api_key",
                claims={"role": "api_client"},
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid API Key provided",
                headers={"WWW-Authenticate": "ApiKey"},
            )

    # 3. Check Authorization Bearer header
    if not authorization:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing Authorization header. Provide a Google Service Account token via 'Bearer <token>' or 'X-API-Key'.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    parts = authorization.split()
    if len(parts) != 2 or parts[0].lower() != "bearer":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid Authorization header format. Expected 'Bearer <token>'.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = parts[1]

    try:
        principal = await verify_google_bearer_token(token, settings)
        return principal
    except ValueError as val_err:
        logger.warning("Authentication failed: %s", val_err)
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Authentication failed: {val_err}",
        )
    except Exception as exc:
        logger.error("Unexpected error verifying token: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal authentication service error",
        )
