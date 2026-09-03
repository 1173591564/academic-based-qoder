"""Scholar service credential resolution without database secret storage."""

import os
import re
from typing import Protocol

ENV_REFERENCE = re.compile(r"^env:([A-Z][A-Z0-9_]{0,127})$")


class SecretResolutionError(RuntimeError):
    """A configured secret reference cannot be resolved."""


class SecretResolver(Protocol):
    """Resolve a deployment-owned reference to secret material."""

    def resolve(self, reference: str) -> str:
        """Return secret material without persisting it."""


class EnvironmentSecretResolver:
    """Resolve explicit env:NAME references for local deployments."""

    def resolve(self, reference: str) -> str:
        """Resolve one strict environment variable reference."""
        match = ENV_REFERENCE.fullmatch(reference)
        if match is None:
            raise SecretResolutionError("unsupported secret reference")
        value = os.environ.get(match.group(1))
        if not value:
            raise SecretResolutionError("secret reference is unavailable")
        return value
