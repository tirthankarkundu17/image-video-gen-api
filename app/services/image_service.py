import base64
from datetime import datetime, timezone
import logging
from typing import List, Optional

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

logger = logging.getLogger(__name__)


def generate_images(
    request: ImageGenerationRequest,
    client: genai.Client,
    settings: Settings,
) -> ImageGenerationResponse:
    """
    Generates images using Vertex AI Imagen models (e.g. imagen-3.0-generate-002).
    """
    model_name = request.model or settings.DEFAULT_IMAGE_MODEL

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
        "Invoking Vertex AI image generation with model='%s', prompt='%s', config=%s",
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

    if not response or not response.generated_images:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Vertex AI returned no images. Prompt may have triggered safety filters or model could not generate content.",
        )

    images: List[GeneratedImageData] = []
    for idx, gen_img in enumerate(response.generated_images):
        mime_type = request.output_mime_type
        base64_str = ""

        if gen_img.image and gen_img.image.image_bytes:
            base64_str = base64.b64encode(gen_img.image.image_bytes).decode("utf-8")
            if gen_img.image.mime_type:
                mime_type = gen_img.image.mime_type
        elif gen_img.image and gen_img.image.gcs_uri:
            # Fallback or reference
            base64_str = gen_img.image.gcs_uri

        images.append(
            GeneratedImageData(
                index=idx + 1,
                mime_type=mime_type,
                base64_data=base64_str,
            )
        )

    return ImageGenerationResponse(
        model=model_name,
        prompt=request.prompt,
        images=images,
        total_images=len(images),
        created_at=datetime.now(timezone.utc).isoformat(),
    )
