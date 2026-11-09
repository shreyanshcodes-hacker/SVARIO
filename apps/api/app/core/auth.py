"""Supabase JWT verification and FastAPI authentication dependencies (Stage 1).

Security Design:
- Never trusts decoded but unverified JWT payloads.
- Prefers asymmetric signature verification (ES256, RS256, EdDSA) via the
  Supabase project's JWKS endpoint (`{SUPABASE_URL}/auth/v1/.well-known/jwks.json`).
- Supports symmetric HS256 verification ONLY when explicitly enabled in
  `SUPABASE_JWT_ALGORITHMS` and `SUPABASE_JWT_SECRET` is configured.
- Strictly validates signature, expiration (`exp`), audience (`aud`),
  issuer (`iss`), and subject UUID (`sub`).
- Never accepts `user_id` from request bodies or query parameters as identity.
"""

from functools import lru_cache
from typing import Any, Callable, Dict, Optional
from uuid import UUID
import jwt
from jwt import PyJWKClient
from jwt.exceptions import InvalidTokenError, PyJWKClientError
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, Field
from app.core.config import Settings, get_settings

bearer_scheme = HTTPBearer(auto_error=False)

ASYMMETRIC_ALGORITHMS = {"ES256", "ES384", "ES512", "RS256", "RS384", "RS512", "EdDSA"}
SYMMETRIC_ALGORITHMS = {"HS256", "HS384", "HS512"}


class AuthenticatedUser(BaseModel):
    """Verified user identity extracted exclusively from a validated Supabase JWT."""

    id: UUID = Field(..., description="Verified Supabase auth.users UUID (`sub` claim)")
    email: Optional[str] = Field(default=None, description="Verified user email claim")
    role: str = Field(default="authenticated", description="Supabase role claim")
    session_id: Optional[str] = Field(default=None, description="Supabase session_id claim")
    issuer: str = Field(..., description="Verified token issuer (`iss`)")
    audience: str = Field(..., description="Verified token audience (`aud`)")
    full_name: Optional[str] = Field(default=None, description="User full_name from user_metadata")
    email_verified: bool = Field(default=False, description="Whether email is verified")
    app_metadata: Dict[str, Any] = Field(default_factory=dict)
    user_metadata: Dict[str, Any] = Field(default_factory=dict)
    raw_token: str = Field(..., exclude=True, repr=False)


def _unauthorized(message: str) -> HTTPException:
    """Construct a standardized HTTP 401 Unauthorized exception."""
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=message,
        headers={"WWW-Authenticate": "Bearer"},
    )


@lru_cache(maxsize=8)
def _get_cached_jwk_client(jwks_url: str) -> PyJWKClient:
    """Return a cached PyJWKClient with key caching enabled."""
    return PyJWKClient(
        jwks_url,
        cache_keys=True,
        max_cached_keys=16,
        headers={"User-Agent": "Svario-API/0.2.0"},
        timeout=10,
    )


class SupabaseJWTVerifier:
    """Verifies Supabase JWT access tokens using JWKS (asymmetric) or explicit secret."""

    def __init__(
        self,
        settings: Settings,
        key_resolver: Optional[Callable[[str, Dict[str, Any]], Any]] = None,
    ) -> None:
        self._settings = settings
        self._key_resolver = key_resolver

    def _resolve_signing_key(self, token: str, header: Dict[str, Any]) -> Any:
        """Resolve verification key for the token based on its algorithm and header."""
        if self._key_resolver is not None:
            return self._key_resolver(token, header)

        alg = str(header.get("alg", "")).strip()
        allowed_algorithms = self._settings.jwt_algorithms

        if not alg or alg.lower() == "none" or alg not in allowed_algorithms:
            raise _unauthorized("Unsupported or disallowed JWT signing algorithm.")

        if alg in ASYMMETRIC_ALGORITHMS:
            jwks_url = self._settings.effective_jwks_url
            if not jwks_url:
                raise _unauthorized(
                    "Asymmetric JWT verification requires SUPABASE_JWKS_URL or SUPABASE_URL."
                )
            try:
                jwk_client = _get_cached_jwk_client(jwks_url)
                signing_key = jwk_client.get_signing_key_from_jwt(token)
                return signing_key.key
            except (PyJWKClientError, InvalidTokenError) as exc:
                raise _unauthorized("Unable to verify token signature against JWKS.") from exc

        if alg in SYMMETRIC_ALGORITHMS:
            secret = self._settings.supabase_jwt_secret
            if not secret or not secret.strip():
                raise _unauthorized(
                    "Symmetric JWT algorithm is not configured on this server."
                )
            return secret.strip()

        raise _unauthorized("Unsupported JWT signing algorithm.")

    def verify_token(self, token: str) -> AuthenticatedUser:
        """Cryptographically verify a Bearer JWT and return an AuthenticatedUser."""
        cleaned_token = token.strip()
        if not cleaned_token:
            raise _unauthorized("Missing authentication token.")

        try:
            unverified_header = jwt.get_unverified_header(cleaned_token)
        except InvalidTokenError as exc:
            raise _unauthorized("Malformed JWT header.") from exc

        alg = str(unverified_header.get("alg", "")).strip()
        if not alg or alg.lower() == "none" or alg not in self._settings.jwt_algorithms:
            raise _unauthorized("Unsupported or disallowed JWT signing algorithm.")

        signing_key = self._resolve_signing_key(cleaned_token, unverified_header)
        expected_issuer = self._settings.effective_jwt_issuer
        expected_audience = self._settings.supabase_jwt_audience

        if not expected_issuer:
            raise _unauthorized(
                "Server authentication issuer (SUPABASE_JWT_ISSUER or SUPABASE_URL) is not configured."
            )

        decode_options = {
            "verify_signature": True,
            "verify_exp": True,
            "verify_nbf": True,
            "verify_iat": True,
            "verify_aud": True,
            "verify_iss": True,
            "require": ["sub", "exp", "aud", "iss"],
        }

        try:
            claims: Dict[str, Any] = jwt.decode(
                cleaned_token,
                key=signing_key,
                algorithms=[alg],
                audience=expected_audience,
                issuer=expected_issuer,
                options=decode_options,
            )
        except jwt.ExpiredSignatureError as exc:
            raise _unauthorized("Authentication token has expired.") from exc
        except jwt.InvalidAudienceError as exc:
            raise _unauthorized("Invalid token audience.") from exc
        except jwt.InvalidIssuerError as exc:
            raise _unauthorized("Invalid token issuer.") from exc
        except InvalidTokenError as exc:
            raise _unauthorized("Invalid authentication token.") from exc

        raw_sub = claims.get("sub")
        if not raw_sub or not isinstance(raw_sub, str):
            raise _unauthorized("Token is missing a valid subject ('sub') claim.")

        try:
            user_uuid = UUID(raw_sub)
        except ValueError as exc:
            raise _unauthorized("Token subject ('sub') must be a valid UUID.") from exc

        user_metadata = claims.get("user_metadata")
        if not isinstance(user_metadata, dict):
            user_metadata = {}

        app_metadata = claims.get("app_metadata")
        if not isinstance(app_metadata, dict):
            app_metadata = {}

        aud_claim = claims.get("aud")
        if isinstance(aud_claim, list):
            resolved_aud = str(aud_claim[0]) if aud_claim else expected_audience
        else:
            resolved_aud = str(aud_claim or expected_audience)

        email_verified = bool(
            user_metadata.get("email_verified")
            or claims.get("email_confirmed_at")
            or user_metadata.get("email_confirmed_at")
        )

        full_name = user_metadata.get("full_name")
        if full_name is not None:
            full_name = str(full_name).strip() or None

        return AuthenticatedUser(
            id=user_uuid,
            email=str(claims["email"]) if claims.get("email") else None,
            role=str(claims.get("role", "authenticated")),
            session_id=str(claims["session_id"]) if claims.get("session_id") else None,
            issuer=str(claims.get("iss", expected_issuer)),
            audience=resolved_aud,
            full_name=full_name,
            email_verified=email_verified,
            app_metadata=app_metadata,
            user_metadata=user_metadata,
            raw_token=cleaned_token,
        )


def get_jwt_verifier(settings: Settings = Depends(get_settings)) -> SupabaseJWTVerifier:
    """FastAPI dependency providing the configured SupabaseJWTVerifier."""
    return SupabaseJWTVerifier(settings=settings)


async def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(bearer_scheme),
    verifier: SupabaseJWTVerifier = Depends(get_jwt_verifier),
) -> AuthenticatedUser:
    """FastAPI dependency that extracts, verifies, and returns the current user.

    1. Extracts Bearer token from Authorization header.
    2. Verifies cryptographic signature (JWKS asymmetric preferred).
    3. Verifies token expiry (`exp`).
    4. Verifies issuer (`iss`) and audience (`aud`).
    5. Rejects missing, malformed, expired, or invalid tokens with HTTP 401.
    6. Returns verified `AuthenticatedUser` identity.
    """
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise _unauthorized("Missing or invalid Authorization Bearer header.")

    if not credentials.credentials or not credentials.credentials.strip():
        raise _unauthorized("Empty Bearer token provided.")

    return verifier.verify_token(credentials.credentials)
