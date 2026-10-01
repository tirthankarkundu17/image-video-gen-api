import asyncio
import base64
from datetime import datetime, timezone
import logging
import time
from typing import Optional
import uuid

from fastapi import HTTPException, status
from google import genai
from google.genai import errors as genai_errors
from google.genai import types

from app.config import Settings, get_settings
from app.schemas.video import VideoGenerationRequest, VideoOperationResponse
from app.services.storage_service import generate_signed_url_for_gcs_uri, upload_video_bytes
from app.services.vertex_client import get_vertex_client_for_location

logger = logging.getLogger(__name__)


def _resolve_video_client(client: genai.Client, settings: Optional[Settings] = None) -> genai.Client:
    """
    Ensures that the client uses a valid regional location for Veo video models.
    Vertex AI Veo models are not available under 'global' and require a regional endpoint (e.g. us-central1).
    """
    from unittest.mock import Mock

    settings = settings or get_settings()
    api_client = getattr(client, "_api_client", None)
    if api_client is not None and not isinstance(api_client, Mock):
        client_location = getattr(api_client, "location", None)
        target_location = settings.GCP_VIDEO_LOCATION or "us-central1"
        if client_location == "global" or (settings.GCP_VIDEO_LOCATION and client_location != settings.GCP_VIDEO_LOCATION):
            logger.info(
                "Veo models require a regional endpoint. Routing client from '%s' to '%s'",
                client_location,
                target_location,
            )
            return get_vertex_client_for_location(target_location, settings)
    return client


def _parse_video_operation_result(
    operation: types.GenerateVideosOperation,
    prompt: Optional[str] = None,
    model: Optional[str] = None,
    created_at: Optional[str] = None,
    settings: Optional[Settings] = None,
    upload_to_gcs: bool = False,
    gcs_bucket: Optional[str] = None,
    gcs_path_prefix: Optional[str] = None,
    include_base64: bool = True,
) -> VideoOperationResponse:
    """Helper to convert a GenerateVideosOperation into VideoOperationResponse."""
    settings = settings or get_settings()
    now_iso = datetime.now(timezone.utc).isoformat()
    created_iso = created_at or now_iso

    if operation.done:
        if operation.error:
            return VideoOperationResponse(
                operation_id=operation.name,
                status="FAILED",
                model=model,
                prompt=prompt,
                error_message=str(operation.error),
                created_at=created_iso,
                updated_at=now_iso,
            )

        video_uri = None
        video_url = None
        video_base64 = None
        mime_type = "video/mp4"
        expiration_mins = settings.GCS_VIDEO_URL_EXPIRATION_MINUTES

        if operation.response and operation.response.generated_videos:
            gen_video = operation.response.generated_videos[0]
            if gen_video.video:
                if gen_video.video.uri:
                    video_uri = gen_video.video.uri
                if gen_video.video.mime_type:
                    mime_type = gen_video.video.mime_type
                if gen_video.video.video_bytes:
                    raw_bytes = gen_video.video.video_bytes
                    if include_base64 or not upload_to_gcs:
                        video_base64 = base64.b64encode(raw_bytes).decode("utf-8")
                    # If upload was requested but model returned bytes instead of writing to GCS directly
                    if upload_to_gcs and not video_uri:
                        target_bucket = gcs_bucket or settings.GCS_VIDEO_BUCKET or settings.GCS_IMAGE_BUCKET
                        if target_bucket:
                            prefix = (gcs_path_prefix or settings.GCS_VIDEO_PATH_PREFIX).strip("/")
                            filename = f"video_{uuid.uuid4().hex[:10]}.mp4"
                            blob_name = f"{prefix}/{filename}" if prefix else filename
                            video_uri, video_url = upload_video_bytes(
                                video_bytes=raw_bytes,
                                bucket_name=target_bucket,
                                destination_blob_name=blob_name,
                                content_type=mime_type,
                                expiration_minutes=expiration_mins,
                                settings=settings,
                            )

        # If we have a GCS URI (either from Vertex AI output_gcs_uri or upload) and haven't generated video_url yet:
        if video_uri and video_uri.startswith("gs://") and not video_url:
            video_url = generate_signed_url_for_gcs_uri(
                gcs_uri=video_uri,
                expiration_minutes=expiration_mins,
                settings=settings,
            )

        return VideoOperationResponse(
            operation_id=operation.name,
            status="COMPLETED",
            model=model,
            prompt=prompt,
            video_uri=video_uri,
            video_url=video_url,
            gcs_url=video_url,
            video_base64=video_base64,
            mime_type=mime_type,
            created_at=created_iso,
            updated_at=now_iso,
        )

    return VideoOperationResponse(
        operation_id=operation.name,
        status="RUNNING",
        model=model,
        prompt=prompt,
        created_at=created_iso,
        updated_at=now_iso,
    )


async def generate_video(
    request: VideoGenerationRequest,
    client: genai.Client,
    settings: Settings,
) -> VideoOperationResponse:
    """
    Initiates video generation using Vertex AI Veo (e.g. veo-3.1-generate-001).
    If request.wait_for_completion is True, polls asynchronously until finished or timeout.
    """
    client = _resolve_video_client(client, settings)
    model_name = request.model or settings.DEFAULT_VIDEO_MODEL
    created_at = datetime.now(timezone.utc).isoformat()

    upload_requested = request.upload_to_gcs or bool(request.output_gcs_uri) or bool(request.gcs_bucket)
    destination_gcs_uri: Optional[str] = None

    if request.output_gcs_uri:
        destination_gcs_uri = request.output_gcs_uri
        if not destination_gcs_uri.endswith("/"):
            destination_gcs_uri += "/"
    elif upload_requested:
        target_bucket = request.gcs_bucket or settings.GCS_VIDEO_BUCKET or settings.GCS_IMAGE_BUCKET
        if not target_bucket:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    "Video generation requested upload_to_gcs=true, but no GCS bucket was configured. "
                    "Please specify 'gcs_bucket' in the request payload or configure 'GCS_VIDEO_BUCKET' / 'GCS_IMAGE_BUCKET' in server settings."
                ),
            )
        prefix = (request.gcs_path_prefix or settings.GCS_VIDEO_PATH_PREFIX).strip("/")
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        destination_gcs_uri = f"gs://{target_bucket}/{prefix}/{timestamp}/"

    config_kwargs = {}
    if request.aspect_ratio:
        config_kwargs["aspect_ratio"] = request.aspect_ratio
    if request.duration_seconds:
        config_kwargs["duration_seconds"] = request.duration_seconds
    if request.fps:
        config_kwargs["fps"] = request.fps
    if request.person_generation:
        config_kwargs["person_generation"] = request.person_generation
    if destination_gcs_uri:
        config_kwargs["output_gcs_uri"] = destination_gcs_uri

    config = types.GenerateVideosConfig(**config_kwargs)

    logger.info(
        "Initiating Vertex AI video generation with model='%s', prompt='%s', config=%s",
        model_name,
        request.prompt,
        config_kwargs,
    )

    try:
        operation = client.models.generate_videos(
            model=model_name,
            prompt=request.prompt,
            config=config,
        )
    except genai_errors.APIError as api_err:
        logger.error("Vertex AI API error during video generation initiation: %s", api_err)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Vertex AI API error: {api_err.message or str(api_err)}",
        )
    except Exception as exc:
        logger.error("Unexpected error during video generation: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Video generation initiation failed: {str(exc)}",
        )

    if not operation or not operation.name:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Failed to obtain operation tracking ID from Vertex AI.",
        )

    # If caller requested async polling on server-side
    if request.wait_for_completion and not operation.done:
        start_time = time.monotonic()
        poll_interval = settings.VIDEO_POLL_INTERVAL_SECONDS
        timeout = settings.VIDEO_POLL_TIMEOUT_SECONDS

        while not operation.done:
            if time.monotonic() - start_time > timeout:
                logger.warning("Video polling timed out after %s seconds", timeout)
                break

            await asyncio.sleep(poll_interval)

            try:
                operation = client.operations.get(operation)
            except Exception as poll_err:
                logger.error("Error polling video operation: %s", poll_err)
                break

    return _parse_video_operation_result(
        operation=operation,
        prompt=request.prompt,
        model=model_name,
        created_at=created_at,
        settings=settings,
        upload_to_gcs=upload_requested,
        gcs_bucket=request.gcs_bucket,
        gcs_path_prefix=request.gcs_path_prefix,
        include_base64=request.include_base64,
    )


def get_video_operation_status(
    operation_id: str,
    client: genai.Client,
    settings: Optional[Settings] = None,
) -> VideoOperationResponse:
    """
    Polls the current status of a Vertex AI video generation operation.
    """
    settings = settings or get_settings()
    client = _resolve_video_client(client, settings)
    # Use model_construct to avoid static type checker warnings where
    # Pylance/Pyright does not recognize fields inherited from Operation (ABC)
    op = types.GenerateVideosOperation.model_construct(name=operation_id)

    try:
        updated_op = client.operations.get(op)
    except genai_errors.APIError as api_err:
        logger.error("Vertex AI API error while getting operation %s: %s", operation_id, api_err)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Vertex AI API error: {api_err.message or str(api_err)}",
        )
    except Exception as exc:
        logger.error("Error retrieving operation %s: %s", operation_id, exc)
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Unable to retrieve video operation '{operation_id}': {str(exc)}",
        )

    return _parse_video_operation_result(operation=updated_op, settings=settings)
