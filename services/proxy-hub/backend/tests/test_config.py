"""Configuration validation tests."""

import pytest
from pydantic import ValidationError

from proxy_hub.config import Settings


def test_production_requires_https_postgres_and_oidc() -> None:
    with pytest.raises(ValidationError):
        Settings(environment="production")


def test_partial_oidc_configuration_is_rejected() -> None:
    with pytest.raises(ValidationError):
        Settings(oidc_client_id="client")


def test_capability_ttl_is_bounded() -> None:
    with pytest.raises(ValidationError):
        Settings(capability_ttl_seconds=299)
    with pytest.raises(ValidationError):
        Settings(capability_ttl_seconds=2_592_001)


def test_gateway_limits_are_bounded() -> None:
    with pytest.raises(ValidationError):
        Settings(backend_probe_max_age_seconds=4)
    with pytest.raises(ValidationError):
        Settings(backend_connect_timeout_seconds=0)
    with pytest.raises(ValidationError):
        Settings(backend_request_timeout_seconds=3_601)
    with pytest.raises(ValidationError):
        Settings(mcp_request_max_bytes=1_023)
    with pytest.raises(ValidationError):
        Settings(quota_reservation_ttl_seconds=29)
    with pytest.raises(ValidationError):
        Settings(quota_reservation_ttl_seconds=7_201)


def test_production_requires_https_oidc_issuer() -> None:
    with pytest.raises(ValidationError, match="OIDC issuer must use HTTPS"):
        Settings(
            environment="production",
            public_origin="https://proxy.example.com",
            oidc_issuer_url="http://identity.example.com",
            oidc_client_id="proxy-hub",
            oidc_client_secret="secret",
            database_url="postgresql+psycopg://proxy-hub@database/proxy-hub",
        )
