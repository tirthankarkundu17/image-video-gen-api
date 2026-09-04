import asyncio
import base64
from datetime import datetime, timezone
import logging
import time
from typing import Optional

from fastapi import HTTPException, status
from google import genai
from google.genai import errors as genai_errors
from google.genai import types

from app.config import Settings
from app.schemas.video import VideoGenerationRequest, VideoOperationResponse

logger = logging.getLogger(__name__)


def _parse_video_operation_result(
    operation: types.GenerateVideosOperation,
    prompt: Optional[str] = None,
    model: Optional[str] = None,
    created_at: Optional[str] = None,
) -> VideoOperationResponse:
    """Helper to convert a GenerateVideosOperation into VideoOperationResponse."""
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
        video_base64 = None
        mime_type = "video/mp4"

        if operation.response and operation.response.generated_videos:
            gen_video = operation.response.generated_videos[0]
            if gen_video.video:
                if gen_video.video.uri:
                    video_uri = gen_video.video.uri
                if gen_video.video.mime_type:
                    mime_type = gen_video.video.mime_type
                if gen_video.video.video_bytes:
                    video_base64 = base64.b64encode(gen_video.video.video_bytes).decode(
                        "utf-8"
                    )

        return VideoOperationResponse(
            operation_id=operation.name,
            status="COMPLETED",
            model=model,
            prompt=prompt,
            video_uri=video_uri,
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
    Initiates video generation using Vertex AI Veo (e.g. veo-2.0-generate-001).
    If request.wait_for_completion is True, polls asynchronously until finished or timeout.
    """
    model_name = request.model or settings.DEFAULT_VIDEO_MODEL
    created_at = datetime.now(timezone.utc).isoformat()

    config_kwargs = {}
    if request.aspect_ratio:
        config_kwargs["aspect_ratio"] = request.aspect_ratio
    if request.duration_seconds:
        config_kwargs["duration_seconds"] = request.duration_seconds
    if request.fps:
        config_kwargs["fps"] = request.fps
    if request.person_generation:
        config_kwargs["person_generation"] = request.person_generation

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
    )


def get_video_operation_status(
    operation_id: str,
    client: genai.Client,
) -> VideoOperationResponse:
    """
    Polls the current status of a Vertex AI video generation operation.
    """
    op = types.GenerateVideosOperation(name=operation_id)

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

    return _parse_video_operation_result(operation=updated_op)
