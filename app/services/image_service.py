import base64
from datetime import datetime, timezone
import logging
from typing import List, Optional
import uuid

from fastapi import HTTPException, status
from google import genai
from google.genai import errors as genai_errors
from google.genai import types

from app.config import Settings
from app.schemas.image import (
    GeneratedImageData,
    ImageGenerationRequest,
    ImageGenerationResponse,
)
from app.services.storage_service import upload_image_bytes

logger = logging.getLogger(__name__)


def generate_images(
    request: ImageGenerationRequest,
    client: genai.Client,
    settings: Settings,
) -> ImageGenerationResponse:
    """
    Generates images using Vertex AI (Gemini multimodal or Imagen models),
    with optional automated upload to Google Cloud Storage.
    """
    model_name = request.model or settings.DEFAULT_IMAGE_MODEL

    # Fail fast if upload_to_gcs is requested but no bucket is available
    if request.upload_to_gcs:
        target_bucket = request.gcs_bucket or settings.GCS_IMAGE_BUCKET
        if not target_bucket:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    "Image generation requested upload_to_gcs=true, but no GCS bucket was configured. "
                    "Please specify 'gcs_bucket' in the request payload or configure 'GCS_IMAGE_BUCKET' in server settings."
                ),
            )

    extracted_images: List[tuple[bytes, str]] = []

    # Check if model is a Gemini image generation model (e.g. gemini-3.1-flash-lite-image)
    if "gemini" in model_name.lower():
        image_config = types.ImageConfig(
            aspect_ratio=request.aspect_ratio or "1:1",
            output_mime_type=request.output_mime_type or "image/png",
        )
        content_config = types.GenerateContentConfig(
            response_modalities=["TEXT", "IMAGE"],
            image_config=image_config,
        )

        logger.info(
            "Invoking Vertex AI Gemini image generation with model='%s', prompt='%s'",
            model_name,
            request.prompt,
        )

        try:
            response = client.models.generate_content(
                model=model_name,
                contents=request.prompt,
                config=content_config,
            )
        except genai_errors.APIError as api_err:
            logger.error("Vertex AI API error during Gemini image generation: %s", api_err)
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"Vertex AI API error: {api_err.message or str(api_err)}",
            )
        except Exception as exc:
            logger.error("Unexpected error during Gemini image generation: %s", exc)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Image generation failed: {str(exc)}",
            )

        if response and response.candidates:
            for candidate in response.candidates:
                if not candidate.content or not candidate.content.parts:
                    continue
                for part in candidate.content.parts:
                    if part.inline_data and part.inline_data.data:
                        mime_type = part.inline_data.mime_type or request.output_mime_type
                        extracted_images.append((part.inline_data.data, mime_type))

    else:
        # Standard Imagen model generation (e.g. imagen-3.0-generate-002)
        config_kwargs = {
            "number_of_images": request.number_of_images,
            "output_mime_type": request.output_mime_type,
        }

        if request.aspect_ratio:
            config_kwargs["aspect_ratio"] = request.aspect_ratio
        if request.negative_prompt:
            config_kwargs["negative_prompt"] = request.negative_prompt
        if request.person_generation:
            config_kwargs["person_generation"] = request.person_generation
        if request.safety_filter_level:
            config_kwargs["safety_filter_level"] = request.safety_filter_level

        config = types.GenerateImagesConfig(**config_kwargs)

        logger.info(
            "Invoking Vertex AI Imagen generation with model='%s', prompt='%s', config=%s",
            model_name,
            request.prompt,
            config_kwargs,
        )

        try:
            response = client.models.generate_images(
                model=model_name,
                prompt=request.prompt,
                config=config,
            )
        except genai_errors.APIError as api_err:
            logger.error("Vertex AI API error during image generation: %s", api_err)
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"Vertex AI API error: {api_err.message or str(api_err)}",
            )
        except Exception as exc:
            logger.error("Unexpected error during image generation: %s", exc)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Image generation failed: {str(exc)}",
            )

        if response and response.generated_images:
            for gen_img in response.generated_images:
                if gen_img.image and gen_img.image.image_bytes:
                    mime_type = gen_img.image.mime_type or request.output_mime_type
                    extracted_images.append((gen_img.image.image_bytes, mime_type))

    if not extracted_images:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Vertex AI returned no images. Prompt may have triggered safety filters or model could not generate content.",
        )

    # Process images: Base64 encoding and optional GCS upload
    batch_id = uuid.uuid4().hex[:8]
    timestamp_str = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    images: List[GeneratedImageData] = []

    for idx, (raw_bytes, mime_type) in enumerate(extracted_images, start=1):
        base64_str: Optional[str] = None
        if request.include_base64 or not request.upload_to_gcs:
            base64_str = base64.b64encode(raw_bytes).decode("utf-8")

        gcs_uri: Optional[str] = None
        gcs_url: Optional[str] = None

        if request.upload_to_gcs:
            bucket_name = request.gcs_bucket or settings.GCS_IMAGE_BUCKET
            prefix = (request.gcs_path_prefix or settings.GCS_PATH_PREFIX).strip("/")
            ext = "png" if "png" in mime_type else "jpg"
            filename = f"{timestamp_str}_{batch_id}_{idx}.{ext}"
            destination_blob = f"{prefix}/{filename}" if prefix else filename

            gcs_uri, gcs_url = upload_image_bytes(
                image_bytes=raw_bytes,
                bucket_name=bucket_name,  # type: ignore[arg-type]
                destination_blob_name=destination_blob,
                content_type=mime_type,
            )

        images.append(
            GeneratedImageData(
                index=idx,
                mime_type=mime_type,
                base64_data=base64_str,
                gcs_uri=gcs_uri,
                gcs_url=gcs_url,
            )
        )

    return ImageGenerationResponse(
        model=model_name,
        prompt=request.prompt,
        images=images,
        total_images=len(images),
        created_at=datetime.now(timezone.utc).isoformat(),
    )
