from functools import lru_cache
from typing import List, Optional
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # GCP / Vertex AI settings
    GCP_PROJECT_ID: Optional[str] = Field(default=None, description="Google Cloud Project ID")
    GCP_LOCATION: str = Field(default="us-central1", description="Vertex AI location/region")
    GCP_VIDEO_LOCATION: Optional[str] = Field(
        default=None,
        description="Optional override location for video models (defaults to GCP_LOCATION, or us-central1 if GCP_LOCATION is global)",
    )
    GCP_SERVICE_ACCOUNT_FILE: Optional[str] = Field(
        default=None, description="Path to GCP Service Account JSON key file"
    )
    GCP_SERVICE_ACCOUNT_INFO: Optional[str] = Field(
        default=None, description="Inline JSON string of GCP Service Account credentials"
    )
    GOOGLE_APPLICATION_CREDENTIALS: Optional[str] = Field(
        default=None, description="Standard GCP credentials env var fallback"
    )

    # Security & Authentication settings
    AUTH_ENABLED: bool = Field(
        default=True,
        description="Whether to enforce caller authentication on protected API endpoints",
    )
    ALLOWED_SERVICE_ACCOUNTS: str = Field(
        default="",
        description="Comma-separated list of service account emails allowed to invoke the API",
    )
    API_KEY: Optional[str] = Field(
        default=None,
        description="Optional static API key for testing / direct programmatic access",
    )

    # Vertex AI Model settings
    DEFAULT_IMAGE_MODEL: str = Field(
        default="imagen-3.0-generate-002", description="Default Imagen model ID"
    )
    DEFAULT_VIDEO_MODEL: str = Field(
        default="veo-3.1-generate-001", description="Default Veo model ID"
    )

    # Google Cloud Storage settings
    GCS_IMAGE_BUCKET: Optional[str] = Field(
        default=None, description="Default Google Cloud Storage bucket for uploading generated images"
    )
    GCS_VIDEO_BUCKET: Optional[str] = Field(
        default=None,
        description="Default Google Cloud Storage bucket for uploading/storing generated videos (falls back to GCS_IMAGE_BUCKET if not set)",
    )
    GCS_PATH_PREFIX: str = Field(
        default="generated-images", description="Default GCS path prefix/folder"
    )
    GCS_VIDEO_PATH_PREFIX: str = Field(
        default="generated-videos", description="Default GCS path prefix/folder for videos"
    )
    GCS_VIDEO_URL_EXPIRATION_MINUTES: int = Field(
        default=30,
        description="Expiration time in minutes for video GCS presigned download URLs (default 30 mins)",
    )

    # Server settings
    HOST: str = Field(default="0.0.0.0", description="Bind host")
    PORT: int = Field(default=8000, description="Bind port")
    DEBUG: bool = Field(default=False, description="Debug mode")

    # Video Polling settings
    VIDEO_POLL_INTERVAL_SECONDS: float = Field(
        default=5.0, description="Interval in seconds for synchronous video polling"
    )
    VIDEO_POLL_TIMEOUT_SECONDS: float = Field(
        default=300.0, description="Timeout in seconds for synchronous video generation wait"
    )

    @property
    def allowed_service_account_list(self) -> List[str]:
        if not self.ALLOWED_SERVICE_ACCOUNTS.strip():
            return []
        return [
            email.strip().lower()
            for email in self.ALLOWED_SERVICE_ACCOUNTS.split(",")
            if email.strip()
        ]


@lru_cache()
def get_settings() -> Settings:
    return Settings()
