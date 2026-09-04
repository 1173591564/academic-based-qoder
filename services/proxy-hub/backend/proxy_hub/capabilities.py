"""Fail-closed DSH Bearer credential authentication."""

from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from proxy_hub.eligibility import active_membership_exists
from proxy_hub.errors import HubError
from proxy_hub.models import AccessKey, DshCapability, Principal, Tenant, utc_now
from proxy_hub.policy import InvalidToolPolicy, validate_tool_policy
from proxy_hub.security import digest_token

ACCESS_KEY_PREFIX = "sk_scholar_v1_"


@dataclass(frozen=True)
class CredentialContext:
    """Authenticated DSH credential metadata without secret material."""

    credential_id: str
    credential_kind: str
    principal_id: str
    tenant_id: str
    scopes: tuple[str, ...]
    expires_at: datetime
    request_limit: int | None = None
    period_seconds: int | None = None

    @property
    def capability_id(self) -> str | None:
        """Return the legacy capability identifier when applicable."""
        return (
            self.credential_id
            if self.credential_kind == "capability"
            else None
        )

    @property
    def access_key_id(self) -> str | None:
        """Return the Access Key identifier when applicable."""
        return (
            self.credential_id
            if self.credential_kind == "access_key"
            else None
        )


CapabilityContext = CredentialContext


def bearer_token(authorization: str | None) -> str:
    """Parse one opaque Bearer credential."""
    if authorization is None:
        raise HubError(
            401,
            "invalid_credential",
            "A valid Scholar credential is required.",
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
            "A valid Scholar credential is required.",
        )
    return token


def _credential_context(
    session: Session,
    *,
    credential_id: str,
    credential_kind: str,
    principal_id: str,
    tenant_id: str,
    raw_scopes: object,
    expires_at: datetime,
    request_limit: int | None = None,
    period_seconds: int | None = None,
) -> CredentialContext:
    """Re-authorize shared tenant and scope requirements."""
    denial_code = (
        "capability_denied"
        if credential_kind == "capability"
        else "credential_denied"
    )
    principal = session.get(Principal, principal_id)
    tenant = session.get(Tenant, tenant_id)
    if (
        principal is None
        or principal.status != "active"
        or tenant is None
        or tenant.status != "active"
        or not active_membership_exists(
            session,
            principal_id,
            tenant_id,
        )
    ):
        raise HubError(
            403,
            denial_code,
            "The Scholar credential is not authorized for an active tenant.",
        )
    try:
        scopes = validate_tool_policy(raw_scopes)
    except InvalidToolPolicy as error:
        raise HubError(
            403,
            denial_code,
            "The Scholar credential contains an invalid tool assignment.",
        ) from error
    if not scopes:
        raise HubError(
            403,
            denial_code,
            "The Scholar credential contains no usable tools.",
        )
    return CredentialContext(
        credential_id=credential_id,
        credential_kind=credential_kind,
        principal_id=principal_id,
        tenant_id=tenant_id,
        scopes=scopes,
        expires_at=expires_at,
        request_limit=request_limit,
        period_seconds=period_seconds,
    )


def authenticate_credential(
    session: Session,
    authorization: str | None,
    *,
    at: datetime | None = None,
) -> CredentialContext:
    """Authenticate a direct Access Key or legacy DSH capability."""
    now = at or utc_now()
    token = bearer_token(authorization)
    token_digest = digest_token(token)
    if token.startswith(ACCESS_KEY_PREFIX):
        access_key = session.scalar(
            select(AccessKey).where(
                AccessKey.token_digest == token_digest,
                AccessKey.revoked_at.is_(None),
                AccessKey.expires_at > now,
            )
        )
        if access_key is None:
            raise HubError(
                401,
                "invalid_credential",
                "A valid Scholar credential is required.",
            )
        return _credential_context(
            session,
            credential_id=access_key.id,
            credential_kind="access_key",
            principal_id=access_key.principal_id,
            tenant_id=access_key.tenant_id,
            raw_scopes=access_key.allowed_tools,
            expires_at=access_key.expires_at,
            request_limit=access_key.request_limit,
            period_seconds=access_key.period_seconds,
        )

    capability = session.scalar(
        select(DshCapability).where(
            DshCapability.token_digest == token_digest,
            DshCapability.revoked_at.is_(None),
            DshCapability.expires_at > now,
        )
    )
    if capability is None:
        raise HubError(
            401,
            "invalid_credential",
            "A valid Scholar credential is required.",
        )
    return _credential_context(
        session,
        credential_id=capability.id,
        credential_kind="capability",
        principal_id=capability.principal_id,
        tenant_id=capability.tenant_id,
        raw_scopes=capability.scopes,
        expires_at=capability.expires_at,
    )


def authenticate_capability(
    session: Session,
    authorization: str | None,
    *,
    at: datetime | None = None,
) -> CredentialContext:
    """Authenticate a Scholar Bearer credential during migration."""
    return authenticate_credential(session, authorization, at=at)
