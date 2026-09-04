"""OIDC browser login and server-side administration sessions."""

from __future__ import annotations

from base64 import urlsafe_b64encode
from collections.abc import Callable, Generator
from dataclasses import dataclass
from datetime import datetime, timedelta
from hashlib import sha256
from typing import cast
from urllib.parse import urlencode, urlparse

import httpx
from fastapi import APIRouter, Cookie, Depends, Header, Query, Request, Response
from fastapi.responses import RedirectResponse
from joserfc import jwt
from joserfc.errors import JoseError
from joserfc.jwk import KeySet, KeySetSerialization
from joserfc.jwt import JWTClaimsRegistry
from sqlalchemy import select
from sqlalchemy.orm import Session

from proxy_hub.audit import AuditEntry, append_audit_event
from proxy_hub.config import Settings
from proxy_hub.database import Database, session_scope
from proxy_hub.errors import HubError, request_id
from proxy_hub.models import (
    BrowserSession,
    Membership,
    OidcLoginState,
    Principal,
    RoleBinding,
    new_id,
    utc_now,
)
from proxy_hub.rbac import PLATFORM_ADMIN, AdminContext, RoleGrant
from proxy_hub.security import digest_token, new_token, token_matches


@dataclass(frozen=True)
class AuthComponents:
    """Authentication routes and reusable authorization dependencies."""

    router: APIRouter
    admin_context: Callable[..., AdminContext]
    mutation_context: Callable[..., AdminContext]


def ensure_utc(value: datetime) -> datetime:
    """Normalize SQLite and PostgreSQL timestamps for comparison."""
    if value.tzinfo is None:
        return value.replace(tzinfo=utc_now().tzinfo)
    return value


def safe_return_to(return_to: str) -> str:
    """Allow redirects only to the local administration console."""
    parsed = urlparse(return_to)
    if (
        parsed.scheme
        or parsed.netloc
        or not parsed.path.startswith("/console/")
        or "\\" in return_to
    ):
        raise HubError(400, "invalid_return_to", "The return path is not allowed.")
    return return_to


def public_origin(settings: Settings) -> str:
    """Return the configured origin without a trailing slash."""
    return str(settings.public_origin).rstrip("/")


def build_auth_components(database: Database, settings: Settings) -> AuthComponents:
    """Build authentication routes and dependencies."""
    router = APIRouter(tags=["authentication"])

    def get_session() -> Generator[Session, None, None]:
        yield from session_scope(database)

    def admin_context(
        proxy_hub_session: str | None = Cookie(
            default=None,
            alias=settings.cookie_name,
        ),
        session: Session = Depends(get_session),
    ) -> AdminContext:
        if not proxy_hub_session:
            raise HubError(
                401,
                "browser_session_required",
                "A valid browser session is required.",
            )
        session_id = digest_token(proxy_hub_session)
        browser_session = session.get(BrowserSession, session_id)
        if (
            browser_session is None
            or browser_session.revoked_at is not None
            or ensure_utc(browser_session.expires_at) <= utc_now()
        ):
            raise HubError(
                401,
                "browser_session_expired",
                "The browser session is absent, expired, or revoked.",
            )
        principal = session.get(Principal, browser_session.principal_id)
        if (
            principal is None
            or principal.kind != "oidc_operator"
            or principal.status != "active"
        ):
            raise HubError(
                403,
                "principal_inactive",
                "The principal is not active.",
            )
        bindings = session.scalars(
            select(RoleBinding).where(
                RoleBinding.principal_id == principal.id,
                RoleBinding.revoked_at.is_(None),
            )
        ).all()
        active_tenant_ids = frozenset(
            session.scalars(
                select(Membership.tenant_id).where(
                    Membership.principal_id == principal.id,
                    Membership.status == "active",
                )
            ).all()
        )
        return AdminContext(
            principal_id=principal.id,
            session_id=browser_session.id,
            csrf_digest=browser_session.csrf_digest,
            grants=tuple(
                RoleGrant(role=binding.role, tenant_id=binding.tenant_id)
                for binding in bindings
                if binding.tenant_id is None or binding.tenant_id in active_tenant_ids
            ),
        )

    def mutation_context(
        request: Request,
        context: AdminContext = Depends(admin_context),
        csrf_header: str | None = Header(default=None, alias="X-CSRF-Token"),
        csrf_cookie: str | None = Cookie(default=None, alias="proxy_hub_csrf"),
        origin: str | None = Header(default=None, alias="Origin"),
    ) -> AdminContext:
        if origin != public_origin(settings):
            raise HubError(
                403,
                "origin_denied",
                "Mutating requests require the configured same origin.",
            )
        if (
            not csrf_header
            or not csrf_cookie
            or csrf_header != csrf_cookie
            or not token_matches(csrf_header, context.csrf_digest)
        ):
            raise HubError(
                403,
                "csrf_denied",
                "The CSRF token is absent or invalid.",
            )
        return context

    @router.get("/auth/login")
    async def login(
        return_to: str = Query(default="/console/"),
        session: Session = Depends(get_session),
    ) -> RedirectResponse:
        if not (
            settings.oidc_issuer_url
            and settings.oidc_client_id
            and settings.oidc_client_secret
        ):
            raise HubError(
                503,
                "oidc_unavailable",
                "OIDC authentication is not configured.",
            )
        target = safe_return_to(return_to)
        discovery = await fetch_discovery(settings)
        state = new_token()
        nonce = new_token()
        verifier = new_token(48)
        challenge = (
            urlsafe_b64encode(sha256(verifier.encode("utf-8")).digest())
            .decode("ascii")
            .rstrip("=")
        )
        session.add(
            OidcLoginState(
                state_digest=digest_token(state),
                nonce=nonce,
                code_verifier=verifier,
                return_to=target,
                expires_at=utc_now() + timedelta(minutes=10),
            )
        )
        query = urlencode(
            {
                "client_id": settings.oidc_client_id,
                "redirect_uri": f"{public_origin(settings)}/auth/callback",
                "response_type": "code",
                "scope": "openid profile email",
                "state": state,
                "nonce": nonce,
                "code_challenge": challenge,
                "code_challenge_method": "S256",
            }
        )
        return RedirectResponse(f"{discovery['authorization_endpoint']}?{query}")

    @router.get("/auth/callback")
    async def callback(
        code: str,
        state: str,
        session: Session = Depends(get_session),
    ) -> RedirectResponse:
        login_state = session.get(OidcLoginState, digest_token(state))
        if login_state is None or ensure_utc(login_state.expires_at) <= utc_now():
            raise HubError(
                400,
                "oidc_state_invalid",
                "The OIDC login state is absent or expired.",
            )
        discovery = await fetch_discovery(settings)
        token_response = await exchange_code(
            settings,
            discovery,
            code,
            login_state.code_verifier,
        )
        claims = await validate_id_token(
            settings,
            discovery,
            token_response,
            login_state.nonce,
        )
        issuer = str(claims["iss"])
        subject = str(claims["sub"])
        email_claim = claims.get("email")
        name_claim = claims.get("name")
        principal = session.scalar(
            select(Principal).where(
                Principal.issuer == issuer,
                Principal.subject == subject,
            )
        )
        if principal is None:
            principal = Principal(
                id=new_id("principal"),
                issuer=issuer,
                subject=subject,
                email=str(email_claim) if email_claim is not None else None,
                display_name=str(name_claim) if name_claim is not None else None,
            )
            session.add(principal)
            session.flush()
            bootstrap_subjects = {
                value.strip()
                for value in settings.bootstrap_platform_admin_subjects.split(",")
                if value.strip()
            }
            if subject in bootstrap_subjects:
                session.add(
                    RoleBinding(
                        id=new_id("role"),
                        principal_id=principal.id,
                        tenant_id=None,
                        role=PLATFORM_ADMIN,
                    )
                )
        raw_session = new_token(48)
        csrf_token = new_token()
        session.add(
            BrowserSession(
                id=digest_token(raw_session),
                principal_id=principal.id,
                csrf_digest=digest_token(csrf_token),
                expires_at=utc_now() + timedelta(seconds=settings.session_ttl_seconds),
            )
        )
        return_to = login_state.return_to
        session.delete(login_state)
        response = RedirectResponse(return_to)
        secure = settings.public_origin.scheme == "https"
        response.set_cookie(
            settings.cookie_name,
            raw_session,
            max_age=settings.session_ttl_seconds,
            secure=secure,
            httponly=True,
            samesite="lax",
            path="/",
        )
        response.set_cookie(
            "proxy_hub_csrf",
            csrf_token,
            max_age=settings.session_ttl_seconds,
            secure=secure,
            httponly=False,
            samesite="lax",
            path="/",
        )
        return response

    @router.post("/v1/admin/logout", status_code=204)
    def logout(
        request: Request,
        response: Response,
        context: AdminContext = Depends(mutation_context),
        session: Session = Depends(get_session),
    ) -> None:
        browser_session = session.get(BrowserSession, context.session_id)
        if browser_session is not None:
            browser_session.revoked_at = utc_now()
        append_audit_event(
            session,
            AuditEntry(
                request_id=request_id(request),
                principal_id=context.principal_id,
                tenant_id=None,
                action="browser_session:logout",
                resource_type="browser_session",
                resource_id=context.session_id,
                outcome="accepted",
                result_class="success",
                details={"result_class": "success"},
            ),
        )
        response.delete_cookie(settings.cookie_name, path="/")
        response.delete_cookie("proxy_hub_csrf", path="/")

    return AuthComponents(
        router=router,
        admin_context=admin_context,
        mutation_context=mutation_context,
    )


async def fetch_discovery(settings: Settings) -> dict[str, str]:
    """Load and validate OIDC provider metadata."""
    if settings.oidc_issuer_url is None:
        raise HubError(503, "oidc_unavailable", "OIDC authentication is unavailable.")
    issuer = str(settings.oidc_issuer_url).rstrip("/")
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.get(f"{issuer}/.well-known/openid-configuration")
            response.raise_for_status()
            payload: object = response.json()
    except (httpx.HTTPError, ValueError) as exc:
        raise HubError(
            503,
            "oidc_unavailable",
            "OIDC provider metadata is unavailable.",
        ) from exc
    required = {"issuer", "authorization_endpoint", "token_endpoint", "jwks_uri"}
    if (
        not isinstance(payload, dict)
        or not required.issubset(payload)
        or str(payload["issuer"]).rstrip("/") != issuer
    ):
        raise HubError(
            503,
            "oidc_metadata_invalid",
            "OIDC provider metadata is invalid.",
        )
    return {key: str(payload[key]) for key in required}


async def exchange_code(
    settings: Settings,
    discovery: dict[str, str],
    code: str,
    verifier: str,
) -> dict[str, object]:
    """Exchange an authorization code without persisting provider tokens."""
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.post(
                discovery["token_endpoint"],
                data={
                    "grant_type": "authorization_code",
                    "code": code,
                    "redirect_uri": f"{public_origin(settings)}/auth/callback",
                    "client_id": settings.oidc_client_id,
                    "client_secret": settings.oidc_client_secret,
                    "code_verifier": verifier,
                },
            )
            response.raise_for_status()
            payload: object = response.json()
    except (httpx.HTTPError, ValueError) as exc:
        raise HubError(
            503,
            "oidc_token_exchange_failed",
            "OIDC token exchange failed.",
        ) from exc
    if not isinstance(payload, dict) or "id_token" not in payload:
        raise HubError(
            503,
            "oidc_token_invalid",
            "OIDC token response did not contain an ID token.",
        )
    return {str(key): value for key, value in payload.items()}


async def validate_id_token(
    settings: Settings,
    discovery: dict[str, str],
    token_response: dict[str, object],
    nonce: str,
) -> dict[str, object]:
    """Verify the provider ID token signature and required claims."""
    expected_issuer = str(settings.oidc_issuer_url).rstrip("/")
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.get(discovery["jwks_uri"])
            response.raise_for_status()
            jwks: object = response.json()
        if not isinstance(jwks, dict):
            raise ValueError("JWKS response must be an object")
        token = jwt.decode(
            str(token_response["id_token"]),
            KeySet.import_key_set(cast(KeySetSerialization, jwks)),
            algorithms=["RS256", "ES256"],
        )
        claims = dict(token.claims)
        JWTClaimsRegistry(
            leeway=60,
            iss={"essential": True, "value": expected_issuer},
            sub={"essential": True},
            aud={"essential": True, "value": settings.oidc_client_id or ""},
            exp={"essential": True},
            nonce={"essential": True, "value": nonce},
        ).validate(claims)
    except (httpx.HTTPError, ValueError, KeyError, JoseError) as exc:
        raise HubError(
            401,
            "oidc_id_token_invalid",
            "OIDC identity validation failed.",
        ) from exc
    return dict(claims)
