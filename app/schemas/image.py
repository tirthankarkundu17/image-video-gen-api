from typing import List, Literal, Optional
from pydantic import BaseModel, Field


AspectRatioLiteral = Literal["1:1", "3:4", "4:3", "9:16", "16:9"]
OutputMimeTypeLiteral = Literal["image/png", "image/jpeg"]
PersonGenerationLiteral = Literal["dont_allow", "allow_adult", "allow_all"]
SafetyFilterLiteral = Literal[
    "block_low_and_above", "block_medium_and_above", "block_only_high", "block_none"
]


class ImageGenerationRequest(BaseModel):
    prompt: str = Field(
        ...,
        min_length=1,
        max_length=2000,
        description="Text description of the image to generate",
        examples=["A cinematic close-up of a futuristic bioluminescent forest at twilight"],
    )
    negative_prompt: Optional[str] = Field(
        default=None,
        max_length=1000,
        description="Text describing elements to avoid in the generated image",
        examples=["blurry, distorted, low quality"],
    )
    aspect_ratio: Optional[AspectRatioLiteral] = Field(
        default="1:1",
        description="Aspect ratio of the generated image",
    )
    number_of_images: int = Field(
        default=1,
        ge=1,
        le=4,
        description="Number of images to generate (1 to 4)",
    )
    output_mime_type: OutputMimeTypeLiteral = Field(
        default="image/png",
        description="MIME type format for generated images",
    )
    person_generation: Optional[PersonGenerationLiteral] = Field(
        default=None,
        description="Policy for generating people",
    )
    safety_filter_level: Optional[SafetyFilterLiteral] = Field(
        default=None,
        description="Safety filter sensitivity level",
    )
    model: Optional[str] = Field(
        default=None,
        description="Vertex AI model identifier (defaults to configured DEFAULT_IMAGE_MODEL)",
        examples=["imagen-3.0-generate-002"],
    )


class GeneratedImageData(BaseModel):
    index: int
    mime_type: str
    base64_data: str


class ImageGenerationResponse(BaseModel):
    model: str
    prompt: str
    images: List[GeneratedImageData]
    total_images: int
    created_at: str
