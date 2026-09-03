"""Deployment-owned secret reference tests."""

import pytest

from proxy_hub.secrets import EnvironmentSecretResolver, SecretResolutionError


def test_environment_secret_resolver_requires_explicit_reference(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    resolver = EnvironmentSecretResolver()
    monkeypatch.setenv("SCHOLAR_TEST_TOKEN", "secret-value")

    assert resolver.resolve("env:SCHOLAR_TEST_TOKEN") == "secret-value"
    with pytest.raises(SecretResolutionError, match="unsupported"):
        resolver.resolve("SCHOLAR_TEST_TOKEN")
    with pytest.raises(SecretResolutionError, match="unavailable"):
        resolver.resolve("env:MISSING_SECRET")
