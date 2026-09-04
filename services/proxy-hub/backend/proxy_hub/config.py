"""Validated Proxy Hub process configuration."""

from functools import lru_cache
from typing import Literal

from pydantic import Field, HttpUrl, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Environment-backed settings for one Proxy Hub process."""

    model_config = SettingsConfigDict(
        env_prefix="PROXY_HUB_",
        env_file=".env",
        extra="ignore",
    )

    environment: Literal["development", "test", "production"] = "development"
    database_url: str = "sqlite:///./proxy-hub.db"
    public_origin: HttpUrl = HttpUrl("http://127.0.0.1:8000")
    cookie_name: str = "proxy_hub_session"
    session_ttl_seconds: int = Field(default=28_800, ge=300, le=2_592_000)
    capability_ttl_seconds: int = Field(default=3_600, ge=300, le=2_592_000)
    backend_probe_max_age_seconds: int = Field(default=300, ge=5, le=3_600)
    backend_probe_max_bytes: int = Field(default=65_536, ge=1_024, le=1_048_576)
    backend_connect_timeout_seconds: float = Field(default=5, ge=0.1, le=60)
    backend_request_timeout_seconds: float = Field(default=300, ge=1, le=3_600)
    mcp_request_max_bytes: int = Field(
        default=1_048_576,
        ge=1_024,
        le=16_777_216,
    )
    mcp_response_max_bytes: int = Field(
        default=16_777_216,
        ge=1_024,
        le=67_108_864,
    )
    quota_reservation_ttl_seconds: int = Field(default=600, ge=30, le=7_200)
    backend_safe_retry_attempts: int = Field(default=1, ge=0, le=3)
    backend_retry_backoff_seconds: float = Field(default=0.1, ge=0, le=1)
    backend_circuit_failure_threshold: int = Field(default=3, ge=1, le=100)
    backend_circuit_recovery_seconds: int = Field(default=30, ge=1, le=3_600)
    audit_failure_policy: Literal["fail_closed"] = "fail_closed"
    audit_retention_days: Literal[180] = 180
    allow_insecure_public_http: bool = False
    single_lab_tenant_id: str | None = None
    single_lab_tenant_slug: str = Field(
        default="scholar-lab",
        pattern=r"^[a-z0-9][a-z0-9-]{1,62}[a-z0-9]$",
    )
    single_lab_tenant_name: str = Field(
        default="Scholar Lab", min_length=1, max_length=200
    )
    single_lab_backend_name: str = Field(
        default="Scholar Backend",
        min_length=1,
        max_length=200,
    )
    single_lab_backend_url: str | None = None
    single_lab_corpus_version: str | None = None
    single_lab_backend_credential_ref: str | None = None
    oidc_issuer_url: HttpUrl | None = None
    oidc_client_id: str | None = None
    oidc_client_secret: str | None = None
    bootstrap_platform_admin_subjects: str = ""

    @field_validator(
        "single_lab_backend_url",
        "single_lab_corpus_version",
        "single_lab_backend_credential_ref",
        mode="before",
    )
    @classmethod
    def empty_single_lab_value_is_unset(cls, value: object) -> object:
        """Treat empty Compose substitutions as absent optional settings."""
        return None if value == "" else value

    @model_validator(mode="after")
    def validate_security(self) -> "Settings":
        """Reject incomplete identity and insecure production settings."""
        oidc_values = (
            self.oidc_issuer_url,
            self.oidc_client_id,
            self.oidc_client_secret,
        )
        if any(oidc_values) and not all(oidc_values):
            raise ValueError(
                "OIDC issuer, client ID, and client secret are required together"
            )
        backend_values = (
            self.single_lab_backend_url,
            self.single_lab_corpus_version,
            self.single_lab_backend_credential_ref,
        )
        if any(backend_values) and not all(backend_values):
            raise ValueError(
                "single-lab backend URL, corpus version, and credential reference "
                "are required together"
            )
        if (
            self.environment != "test"
            and self.public_origin.scheme == "http"
            and self.public_origin.host not in {"127.0.0.1", "localhost", "::1"}
            and not self.allow_insecure_public_http
        ):
            raise ValueError(
                "public HTTP requires PROXY_HUB_ALLOW_INSECURE_PUBLIC_HTTP=true"
            )
        if self.environment == "production":
            if self.public_origin.scheme != "https":
                raise ValueError("production public origin must use HTTPS")
            if not all(oidc_values):
                raise ValueError("production requires OIDC configuration")
            if self.oidc_issuer_url and self.oidc_issuer_url.scheme != "https":
                raise ValueError("production OIDC issuer must use HTTPS")
            if self.database_url.startswith("sqlite"):
                raise ValueError("production requires PostgreSQL")
            if not self.cookie_name.startswith("__Host-"):
                raise ValueError(
                    "production browser session cookie must use the __Host- prefix"
                )
            if (
                self.oidc_client_secret is None
                or len(self.oidc_client_secret) < 16
                or "replace" in self.oidc_client_secret.casefold()
            ):
                raise ValueError(
                    "production requires a non-placeholder OIDC client secret"
                )
            if self.backend_connect_timeout_seconds > 10:
                raise ValueError(
                    "production backend connect timeout must not exceed 10 seconds"
                )
        return self


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return the process settings."""
    return Settings()
