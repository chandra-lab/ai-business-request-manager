"""FastAPI application entrypoint."""

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app import __version__
from app.api.routes import auth, dashboard, departments, health, hr, manager, requests, review
from app.core.config import get_settings
from app.core.logging import configure_logging, get_logger

# Ensure models are registered on Base.metadata
import app.models  # noqa: F401


@asynccontextmanager
async def lifespan(_app: FastAPI):
    settings = get_settings()
    configure_logging(settings.log_level)
    logger = get_logger(__name__)
    Path(settings.upload_dir).mkdir(parents=True, exist_ok=True)
    logger.info(
        "Starting %s v%s (env=%s, ai_provider=%s)",
        settings.app_name,
        __version__,
        settings.app_env,
        settings.ai_provider,
    )
    yield
    logger.info("Shutting down %s", settings.app_name)


def create_app() -> FastAPI:
    settings = get_settings()
    application = FastAPI(
        title=settings.app_name,
        description=(
            "AI Business Request Manager — internal request routing for an automotive group. "
            "Phase 5: department/HR authorization, case grants, audit logging."
        ),
        version=__version__,
        lifespan=lifespan,
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
    )

    application.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    application.include_router(health.router)
    application.include_router(auth.router, prefix=settings.api_v1_prefix)
    application.include_router(requests.router, prefix=settings.api_v1_prefix)
    application.include_router(dashboard.router, prefix=settings.api_v1_prefix)
    application.include_router(review.router, prefix=settings.api_v1_prefix)
    application.include_router(manager.router, prefix=settings.api_v1_prefix)
    application.include_router(departments.router, prefix=settings.api_v1_prefix)
    application.include_router(hr.router, prefix=settings.api_v1_prefix)

    return application


app = create_app()
