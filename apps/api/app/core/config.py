"""Environment-based Pydantic configuration for Svario API (Stage 0, Stage 1, Stage 2 & Stage 3)."""

from functools import lru_cache
from pathlib import Path
from typing import List, Optional
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

_API_DIR = Path(__file__).resolve().parents[2]
_REPO_ROOT = _API_DIR.parent.parent

ALLOWED_REALTIME_VOICES = {
    "alloy",
    "ash",
    "ballad",
    "coral",
    "echo",
    "sage",
    "shimmer",
    "verse",
    "marin",
    "cedar",
}


class Settings(BaseSettings):
    """Application settings loaded from environment variables or .env file."""

    model_config = SettingsConfigDict(
        env_file=(
            str(_API_DIR / ".env"),
            str(_REPO_ROOT / ".env"),
            ".env",
        ),
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    svario_env: str = Field(default="development", validation_alias="SVARIO_ENV")
    svario_stage: int = Field(default=0, validation_alias="SVARIO_STAGE")
    api_service_name: str = Field(default="Svario API", validation_alias="API_SERVICE_NAME")
    api_version: str = Field(default="0.3.0", validation_alias="API_VERSION")
    api_host: str = Field(default="0.0.0.0", validation_alias="API_HOST")
    api_port: int = Field(default=8000, validation_alias="API_PORT")
    cors_origins_raw: str = Field(
        default="http://localhost:3000,http://127.0.0.1:3000",
        validation_alias="CORS_ORIGINS",
    )

    # --- Stage 1: Supabase & JWT Verification Configuration ---
    supabase_url: Optional[str] = Field(default=None, validation_alias="SUPABASE_URL")
    supabase_anon_key: Optional[str] = Field(
        default=None, validation_alias="SUPABASE_ANON_KEY"
    )
    supabase_service_role_key: Optional[str] = Field(
        default=None, validation_alias="SUPABASE_SERVICE_ROLE_KEY"
    )
    supabase_jwks_url: Optional[str] = Field(
        default=None, validation_alias="SUPABASE_JWKS_URL"
    )
    supabase_jwt_issuer: Optional[str] = Field(
        default=None, validation_alias="SUPABASE_JWT_ISSUER"
    )
    supabase_jwt_audience: str = Field(
        default="authenticated", validation_alias="SUPABASE_JWT_AUDIENCE"
    )
    supabase_jwt_algorithms_raw: str = Field(
        default="ES256,RS256,EdDSA",
        validation_alias="SUPABASE_JWT_ALGORITHMS",
    )
    supabase_jwt_secret: Optional[str] = Field(
        default=None, validation_alias="SUPABASE_JWT_SECRET"
    )
    database_url: Optional[str] = Field(default=None, validation_alias="DATABASE_URL")

    # --- Stage 3: OpenAI Realtime Voice Infrastructure Configuration ---
    openai_api_key: Optional[str] = Field(
        default=None,
        validation_alias="OPENAI_API_KEY",
        repr=False,
    )
    openai_realtime_model: str = Field(
        default="gpt-4o-realtime-preview",
        validation_alias="OPENAI_REALTIME_MODEL",
    )
    openai_realtime_voice: str = Field(
        default="alloy",
        validation_alias="OPENAI_REALTIME_VOICE",
    )
    openai_realtime_api_base_url: str = Field(
        default="https://api.openai.com/v1",
        validation_alias="OPENAI_REALTIME_API_BASE_URL",
    )
    openai_realtime_session_ttl_seconds: int = Field(
        default=120,
        ge=30,
        le=600,
        validation_alias="OPENAI_REALTIME_SESSION_TTL_SECONDS",
    )
    openai_realtime_modalities_raw: str = Field(
        default="audio,text",
        validation_alias="OPENAI_REALTIME_MODALITIES",
    )
    voice_session_rate_limit_per_minute: int = Field(
        default=10,
        ge=1,
        le=120,
        validation_alias="VOICE_SESSION_RATE_LIMIT_PER_MINUTE",
    )
    voice_public_token_secret: Optional[str] = Field(
        default=None,
        validation_alias="VOICE_PUBLIC_TOKEN_SECRET",
        repr=False,
    )
    voice_public_token_ttl_seconds: int = Field(
        default=3600,
        ge=60,
        le=86400,
        validation_alias="VOICE_PUBLIC_TOKEN_TTL_SECONDS",
    )

    @field_validator("svario_stage")
    @classmethod
    def validate_stage(cls, value: int) -> int:
        if value < 0:
            raise ValueError("SVARIO_STAGE must be a non-negative integer.")
        return value

    @field_validator("openai_realtime_voice")
    @classmethod
    def validate_realtime_voice(cls, value: str) -> str:
        cleaned = value.strip().lower()
        if cleaned not in ALLOWED_REALTIME_VOICES:
            raise ValueError(
                f"OPENAI_REALTIME_VOICE must be one of {sorted(ALLOWED_REALTIME_VOICES)}."
            )
        return cleaned

    @field_validator("openai_realtime_model")
    @classmethod
    def validate_realtime_model(cls, value: str) -> str:
        cleaned = value.strip()
        if len(cleaned) < 3:
            raise ValueError("OPENAI_REALTIME_MODEL must be a valid model identifier.")
        return cleaned

    @property
    def cors_origins(self) -> List[str]:
        """Parse comma-separated CORS origins into a clean list."""
        return [
            origin.strip()
            for origin in self.cors_origins_raw.split(",")
            if origin.strip()
        ]

    @property
    def jwt_algorithms(self) -> List[str]:
        """Return list of permitted JWT signing algorithms."""
        return [
            alg.strip()
            for alg in self.supabase_jwt_algorithms_raw.split(",")
            if alg.strip()
        ]

    @property
    def effective_jwks_url(self) -> Optional[str]:
        """Resolve explicit JWKS URL or derive it from SUPABASE_URL."""
        if self.supabase_jwks_url and self.supabase_jwks_url.strip():
            return self.supabase_jwks_url.strip()
        if self.supabase_url and self.supabase_url.strip():
            base = self.supabase_url.strip().rstrip("/")
            if "your-project-ref" not in base:
                return f"{base}/auth/v1/.well-known/jwks.json"
        return None

    @property
    def effective_jwt_issuer(self) -> Optional[str]:
        """Resolve explicit JWT issuer or derive it from SUPABASE_URL."""
        if self.supabase_jwt_issuer and self.supabase_jwt_issuer.strip():
            return self.supabase_jwt_issuer.strip()
        if self.supabase_url and self.supabase_url.strip():
            base = self.supabase_url.strip().rstrip("/")
            if "your-project-ref" not in base:
                return f"{base}/auth/v1"
        return None

    @property
    def is_live_supabase_configured(self) -> bool:
        """Check whether real Supabase project URL and key are configured."""
        if not self.supabase_url or not self.supabase_anon_key:
            return False
        return (
            "your-project-ref" not in self.supabase_url
            and "placeholder" not in self.supabase_anon_key
        )

    @property
    def is_openai_configured(self) -> bool:
        """Check whether a non-placeholder backend OpenAI API key is configured."""
        if not self.openai_api_key:
            return False
        cleaned = self.openai_api_key.strip()
        if not cleaned or "placeholder" in cleaned.lower() or cleaned.startswith("your-"):
            return False
        return True

    @property
    def realtime_modalities(self) -> List[str]:
        """Return allowed OpenAI Realtime session modalities (audio, text)."""
        allowed = {"audio", "text"}
        parsed = [
            item.strip().lower()
            for item in self.openai_realtime_modalities_raw.split(",")
            if item.strip().lower() in allowed
        ]
        return parsed if parsed else ["audio", "text"]

    @property
    def effective_realtime_base_url(self) -> str:
        """Return normalized OpenAI Realtime base URL without trailing slash."""
        return self.openai_realtime_api_base_url.strip().rstrip("/")


@lru_cache
def get_settings() -> Settings:
    """Return cached application settings instance."""
    return Settings()
