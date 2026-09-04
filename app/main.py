from contextlib import asynccontextmanager
import logging
from typing import AsyncGenerator

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config import get_settings
from app.routers.health import router as health_router
from app.routers.images import router as images_router
from app.routers.videos import router as videos_router
from app.services.vertex_client import get_vertex_client

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger("app")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Lifespan context manager for startup and shutdown hooks."""
    settings = get_settings()
    logger.info("Starting Vertex AI Image & Video Generation API...")
    logger.info("Configured Project ID: %s", settings.GCP_PROJECT_ID or "(ADC / Not set)")
    logger.info("Configured Location: %s", settings.GCP_LOCATION)
    logger.info("Authentication Enabled: %s", settings.AUTH_ENABLED)

    # Attempt pre-warming client if configured
    try:
        if settings.GCP_PROJECT_ID:
            get_vertex_client(settings)
            logger.info("Vertex AI client initialized successfully during startup.")
    except Exception as e:
        logger.warning("Vertex AI client could not pre-initialize at startup: %s", e)

    yield

    logger.info("Shutting down Vertex AI Image & Video Generation API...")


def create_app() -> FastAPI:
    """Application factory."""
    settings = get_settings()

    app = FastAPI(
        title="Vertex AI Image & Video Generation API",
        description=(
            "A production-grade REST API utilizing Google Cloud Vertex AI (Imagen 3 and Veo) "
            "for prompt-based image and video generation, secured with GCP Service Account authentication."
        ),
        version="0.1.0",
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
        lifespan=lifespan,
    )

    # Enable CORS for cross-origin client apps
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Global Exception Handler
    @app.exception_handler(Exception)
    async def global_exception_handler(request: Request, exc: Exception):
        logger.exception("Unhandled server error: %s", exc)
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "code": "INTERNAL_SERVER_ERROR",
                "message": "An unexpected error occurred processing your request.",
                "details": str(exc) if settings.DEBUG else None,
            },
        )

    # Include API routers
    app.include_router(health_router)
    app.include_router(images_router)
    app.include_router(videos_router)

    return app


app = create_app()
