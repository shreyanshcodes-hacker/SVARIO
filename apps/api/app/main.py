"""FastAPI application entrypoint for Svario API (Stage 0 — Product Foundation)."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import get_settings
from app.core.errors import register_exception_handlers
from app.routes import api_router


def create_app() -> FastAPI:
    """Instantiate and configure the Svario FastAPI application."""
    settings = get_settings()

    if (
        settings.svario_env.strip().lower() == "production"
        and not settings.is_live_supabase_configured
    ):
        raise RuntimeError(
            "Startup aborted: SVARIO_ENV=production requires live Supabase configuration "
            "(SUPABASE_URL and SUPABASE_ANON_KEY). Ephemeral in-memory storage is forbidden in production."
        )

    application = FastAPI(
        title=settings.api_service_name,
        description=(
            "SVARIO — AI that speaks for your business. "
            "Multi-industry AI Voice Agent Platform (Salons, Clinics, Hospitals). "
            "Stage 0: Product Foundation."
        ),
        version=settings.api_version,
        docs_url="/docs",
        redoc_url="/redoc",
    )

    application.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_origin_regex=r"^https?://(localhost|127\.0\.0\.1)(:\d+)?$",
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["*"],
    )

    register_exception_handlers(application)
    application.include_router(api_router)

    return application


app = create_app()
