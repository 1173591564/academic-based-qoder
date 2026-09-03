"""Fail-closed DSH Bearer capability authentication."""

from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from proxy_hub.eligibility import active_membership_exists
from proxy_hub.errors import HubError
from proxy_hub.models import DshCapability, Principal, Tenant, utc_now
from proxy_hub.policy import InvalidToolPolicy, validate_tool_policy
from proxy_hub.security import digest_token


@dataclass(frozen=True)
class CapabilityContext:
    """Authenticated DSH capability metadata without credential material."""

    capability_id: str
    principal_id: str
    tenant_id: str
    scopes: tuple[str, ...]
    expires_at: datetime


def bearer_token(authorization: str | None) -> str:
    """Parse one opaque Bearer credential."""
    if authorization is None:
        raise HubError(
            401,
            "invalid_credential",
            "A valid DSH session capability is required.",
        )
    scheme, separator, token = authorization.partition(" ")
    if (
        separator != " "
        or scheme.casefold() != "bearer"
        or not token
        or token.strip() != token
        or " " in token
        or len(token) > 512
    ):
        raise HubError(
            401,
            "invalid_credential",
            "A valid DSH session capability is required.",
        )
    return token


def authenticate_capability(
    session: Session,
    authorization: str | None,
    *,
    at: datetime | None = None,
) -> CapabilityContext:
    """Authenticate and re-authorize one DSH capability."""
    now = at or utc_now()
    token = bearer_token(authorization)
    capability = session.scalar(
        select(DshCapability).where(
            DshCapability.token_digest == digest_token(token),
            DshCapability.revoked_at.is_(None),
            DshCapability.expires_at > now,
        )
    )
    if capability is None:
        raise HubError(
            401,
            "invalid_credential",
            "A valid DSH session capability is required.",
        )

    principal = session.get(Principal, capability.principal_id)
    tenant = session.get(Tenant, capability.tenant_id)
    if (
        principal is None
        or principal.status != "active"
        or tenant is None
        or tenant.status != "active"
        or not active_membership_exists(
            session,
            capability.principal_id,
            capability.tenant_id,
        )
    ):
        raise HubError(
            403,
            "capability_denied",
            "The DSH session is not authorized for an active tenant.",
        )
    try:
        scopes = validate_tool_policy(capability.scopes)
    except InvalidToolPolicy as error:
        raise HubError(
            403,
            "capability_denied",
            "The DSH session contains an invalid scope assignment.",
        ) from error
    if not scopes:
        raise HubError(
            403,
            "capability_denied",
            "The DSH session contains no usable scopes.",
        )
    return CapabilityContext(
        capability_id=capability.id,
        principal_id=capability.principal_id,
        tenant_id=capability.tenant_id,
        scopes=scopes,
        expires_at=capability.expires_at,
    )
