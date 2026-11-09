"""Environment-based Pydantic configuration for Svario API (Stage 0 & Stage 1)."""

from functools import lru_cache
from pathlib import Path
from typing import List, Optional
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

_API_DIR = Path(__file__).resolve().parents[2]
_REPO_ROOT = _API_DIR.parent.parent


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
    api_version: str = Field(default="0.2.0", validation_alias="API_VERSION")
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

    @field_validator("svario_stage")
    @classmethod
    def validate_stage(cls, value: int) -> int:
        if value < 0:
            raise ValueError("SVARIO_STAGE must be a non-negative integer.")
        return value

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


@lru_cache
def get_settings() -> Settings:
    """Return cached application settings instance."""
    return Settings()
