"""Environment-based Pydantic configuration for Svario API (Stage 0, Stage 1, Stage 2 & Stage 3)."""

from functools import lru_cache
import ipaddress
from pathlib import Path
from typing import List, Optional, Tuple, Union
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
    trusted_proxies_raw: str = Field(
        default="",
        validation_alias="TRUSTED_PROXIES",
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
        default="gpt-realtime",
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

    # --- Stage 3B-2: Distributed Redis State Configuration (Upstash REST) ---
    upstash_redis_rest_url: Optional[str] = Field(
        default=None,
        validation_alias="UPSTASH_REDIS_REST_URL",
    )
    upstash_redis_rest_token: Optional[str] = Field(
        default=None,
        validation_alias="UPSTASH_REDIS_REST_TOKEN",
        repr=False,
    )
    redis_timeout_seconds: float = Field(
        default=2.0,
        ge=0.2,
        le=10.0,
        validation_alias="REDIS_TIMEOUT_SECONDS",
    )

    # --- Stage 12B: SMS Reminder Engine Foundation (Noop-only, disabled by default) ---
    sms_reminders_enabled: bool = Field(
        default=False,
        validation_alias="SMS_REMINDERS_ENABLED",
    )
    sms_provider: str = Field(
        default="noop",
        validation_alias="SMS_PROVIDER",
    )
    sms_worker_poll_interval_seconds: int = Field(
        default=30,
        ge=5,
        le=300,
        validation_alias="SMS_WORKER_POLL_INTERVAL_SECONDS",
    )
    sms_worker_batch_size: int = Field(
        default=25,
        ge=1,
        le=100,
        validation_alias="SMS_WORKER_BATCH_SIZE",
    )
    sms_worker_lease_timeout_seconds: int = Field(
        default=300,
        ge=30,
        le=3600,
        validation_alias="SMS_WORKER_LEASE_TIMEOUT_SECONDS",
    )
    sms_reminder_lead_minutes: int = Field(
        default=30,
        ge=5,
        le=1440,
        validation_alias="SMS_REMINDER_LEAD_MINUTES",
    )
    sms_default_country_code: Optional[str] = Field(
        default=None,
        validation_alias="SMS_DEFAULT_COUNTRY_CODE",
    )

    # --- Stage 12C.1: MSG91 Provider Configuration (inactive while SMS_REMINDERS_ENABLED=false) ---
    msg91_api_key: Optional[str] = Field(
        default=None,
        validation_alias="MSG91_API_KEY",
        repr=False,
    )
    msg91_api_base_url: str = Field(
        default="https://control.msg91.com/api/v5/flow",
        validation_alias="MSG91_API_BASE_URL",
    )
    msg91_sender_id: Optional[str] = Field(
        default=None,
        validation_alias="MSG91_SENDER_ID",
    )
    msg91_dlt_entity_id: Optional[str] = Field(
        default=None,
        validation_alias="MSG91_DLT_ENTITY_ID",
    )
    msg91_template_id_customer_30m: Optional[str] = Field(
        default=None,
        validation_alias="MSG91_TEMPLATE_ID_CUSTOMER_30M",
    )
    msg91_template_id_owner_30m: Optional[str] = Field(
        default=None,
        validation_alias="MSG91_TEMPLATE_ID_OWNER_30M",
    )
    msg91_template_id_staff_30m: Optional[str] = Field(
        default=None,
        validation_alias="MSG91_TEMPLATE_ID_STAFF_30M",
    )
    msg91_connect_timeout_seconds: float = Field(
        default=5.0,
        ge=1.0,
        le=30.0,
        validation_alias="MSG91_CONNECT_TIMEOUT_SECONDS",
    )
    msg91_read_timeout_seconds: float = Field(
        default=10.0,
        ge=1.0,
        le=60.0,
        validation_alias="MSG91_READ_TIMEOUT_SECONDS",
    )
    msg91_write_timeout_seconds: float = Field(
        default=5.0,
        ge=1.0,
        le=30.0,
        validation_alias="MSG91_WRITE_TIMEOUT_SECONDS",
    )

    # --- Stage 12C.2: MSG91 DLR Webhook & SMS Logs Reconciliation (disabled by default) ---
    msg91_webhook_secret: Optional[str] = Field(
        default=None,
        validation_alias="MSG91_WEBHOOK_SECRET",
        repr=False,
    )
    msg91_webhook_timezone: str = Field(
        default="Asia/Kolkata",
        validation_alias="MSG91_WEBHOOK_TIMEZONE",
    )
    msg91_webhook_max_body_bytes: int = Field(
        default=65536,
        ge=1024,
        le=524288,
        validation_alias="MSG91_WEBHOOK_MAX_BODY_BYTES",
    )
    msg91_logs_reconciliation_enabled: bool = Field(
        default=False,
        validation_alias="MSG91_LOGS_RECONCILIATION_ENABLED",
    )
    msg91_logs_api_url: str = Field(
        default="https://control.msg91.com/api/v5/report/logs/p/sms",
        validation_alias="MSG91_LOGS_API_URL",
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

    @field_validator("trusted_proxies_raw")
    @classmethod
    def validate_trusted_proxies(cls, value: str) -> str:
        """Validate comma-separated IPv4/IPv6 addresses or CIDR ranges."""
        for raw_entry in (value or "").split(","):
            entry = raw_entry.strip()
            if not entry:
                continue
            try:
                ipaddress.ip_network(entry, strict=False)
            except ValueError as exc:
                raise ValueError(
                    f"Invalid TRUSTED_PROXIES entry '{entry}': must be a valid IPv4/IPv6 address or CIDR range."
                ) from exc
        return value

    @property
    def trusted_proxy_networks(
        self,
    ) -> Tuple[Union[ipaddress.IPv4Network, ipaddress.IPv6Network], ...]:
        """Return parsed trusted proxy IPv4/IPv6 networks."""
        networks: List[Union[ipaddress.IPv4Network, ipaddress.IPv6Network]] = []
        for raw_entry in (self.trusted_proxies_raw or "").split(","):
            entry = raw_entry.strip()
            if not entry:
                continue
            networks.append(ipaddress.ip_network(entry, strict=False))
        return tuple(networks)

    @property
    def normalized_env(self) -> str:
        """Return normalized lowercase SVARIO_ENV string."""
        return (self.svario_env or "development").strip().lower()

    @property
    def is_production(self) -> bool:
        """Return True when SVARIO_ENV is normalized to 'production'."""
        return self.normalized_env == "production"

    @property
    def is_upstash_redis_configured(self) -> bool:
        """Return True when non-placeholder Upstash REST URL and token are set."""
        url = (self.upstash_redis_rest_url or "").strip()
        tok = (self.upstash_redis_rest_token or "").strip()
        if not url or not tok:
            return False
        if "placeholder" in url.lower() or "placeholder" in tok.lower() or tok.startswith("your-"):
            return False
        return True

    @property
    def is_redis_configured(self) -> bool:
        """Return True when Upstash Redis REST is configured."""
        return self.is_upstash_redis_configured

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


@lru_cache(maxsize=4)
def _load_settings_cached(_env_mtime_ns: int) -> Settings:
    """Internal cached settings loader keyed by .env modification timestamp."""
    return Settings()


def get_settings() -> Settings:
    """Return application settings instance, automatically reloading if .env changes."""
    env_path = _API_DIR / ".env"
    try:
        mtime_ns = env_path.stat().st_mtime_ns if env_path.exists() else 0
    except OSError:
        mtime_ns = 0
    return _load_settings_cached(mtime_ns)


# Provide cache_clear() compatibility for tests
get_settings.cache_clear = _load_settings_cached.cache_clear  # type: ignore[attr-defined]
