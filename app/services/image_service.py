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

    images: List[GeneratedImageData] = []

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
                        base64_str = base64.b64encode(part.inline_data.data).decode("utf-8")
                        mime_type = part.inline_data.mime_type or request.output_mime_type
                        images.append(
                            GeneratedImageData(
                                index=len(images) + 1,
                                mime_type=mime_type,
                                base64_data=base64_str,
                            )
                        )

        if not images:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="Vertex AI returned no images. Prompt may have triggered safety filters or model could not generate content.",
            )

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

        if not response or not response.generated_images:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="Vertex AI returned no images. Prompt may have triggered safety filters or model could not generate content.",
            )

        for idx, gen_img in enumerate(response.generated_images):
            mime_type = request.output_mime_type
            base64_str = ""

            if gen_img.image and gen_img.image.image_bytes:
                base64_str = base64.b64encode(gen_img.image.image_bytes).decode("utf-8")
                if gen_img.image.mime_type:
                    mime_type = gen_img.image.mime_type
            elif gen_img.image and gen_img.image.gcs_uri:
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
