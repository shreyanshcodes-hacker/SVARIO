"""FastAPI application entrypoint for Svario API (Stage 0 — Product Foundation)."""

from contextlib import asynccontextmanager
from typing import AsyncIterator, Optional
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import Settings, get_settings
from app.core.errors import register_exception_handlers
from app.core.redis_provider import (
    close_redis_client,
    init_redis_client,
    validate_production_redis_config,
)
from app.modules.voice.public_access import validate_production_public_voice_secret
from app.routes import api_router

ALLOWED_CORS_HEADERS = [
    "Authorization",
    "Content-Type",
    "Accept",
    "X-Webhook-Secret",
]

LOCALHOST_CORS_ORIGIN_REGEX = r"^https?://(localhost|127\.0\.0\.1)(:\d+)?$"


def create_app(settings: Optional[Settings] = None) -> FastAPI:
    """Instantiate and configure the Svario FastAPI application."""
    resolved_settings = settings or get_settings()

    if resolved_settings.is_production:
        if not resolved_settings.is_live_supabase_configured:
            raise RuntimeError(
                "Startup aborted: SVARIO_ENV=production requires live Supabase configuration "
                "(SUPABASE_URL and SUPABASE_ANON_KEY). Ephemeral in-memory storage is forbidden in production."
            )
        validate_production_public_voice_secret(resolved_settings)
        validate_production_redis_config(resolved_settings)

    allowed_origins = [
        origin for origin in resolved_settings.cors_origins if origin != "*"
    ]
    origin_regex = None if resolved_settings.is_production else LOCALHOST_CORS_ORIGIN_REGEX

    @asynccontextmanager
    async def lifespan(app_instance: FastAPI) -> AsyncIterator[None]:
        instance_redis_client = init_redis_client(resolved_settings)
        app_instance.state.redis_client = instance_redis_client
        try:
            yield
        finally:
            close_redis_client(instance_redis_client)
            app_instance.state.redis_client = None

    application = FastAPI(
        title=resolved_settings.api_service_name,
        description=(
            "SVARIO — AI that speaks for your business. "
            "Multi-industry AI Voice Agent Platform (Salons, Clinics, Hospitals). "
            "Stage 0: Product Foundation."
        ),
        version=resolved_settings.api_version,
        docs_url="/docs",
        redoc_url="/redoc",
        lifespan=lifespan,
    )

    application.add_middleware(
        CORSMiddleware,
        allow_origins=allowed_origins,
        allow_origin_regex=origin_regex,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=ALLOWED_CORS_HEADERS,
    )

    register_exception_handlers(application)
    application.include_router(api_router)

    return application


app = create_app()
