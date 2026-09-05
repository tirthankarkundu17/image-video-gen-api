from typing import Any, Dict, Optional
from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    status: str = Field(default="healthy", description="Overall health status")
    version: str = Field(default="0.1.0", description="API version")
    timestamp: str = Field(..., description="UTC timestamp of the check")


class ReadinessResponse(BaseModel):
    status: str = Field(..., description="Readiness status (ready or degraded)")
    gcp_project_id: Optional[str] = Field(default=None, description="Configured GCP Project ID")
    gcp_location: str = Field(..., description="Configured Vertex AI region")
    auth_enabled: bool = Field(..., description="Whether API client auth is enabled")
    vertex_client_ready: bool = Field(..., description="Whether Vertex AI client is initialized")
    details: Optional[Dict[str, Any]] = None


class ErrorDetail(BaseModel):
    code: str
    message: str
    details: Optional[Dict[str, Any]] = None
