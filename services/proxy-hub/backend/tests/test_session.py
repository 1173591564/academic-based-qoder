"""DSH session exchange and capability authentication tests."""

from dataclasses import dataclass
from datetime import timedelta

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from proxy_hub.capabilities import authenticate_capability
from proxy_hub.errors import HubError
from proxy_hub.models import (
    AuditEvent,
    DshCapability,
    EnrolmentToken,
    Membership,
    Principal,
    QuotaPolicy,
    QuotaWindow,
    Team,
    Tenant,
    new_id,
    utc_now,
)
from proxy_hub.quota import quota_window_start
from proxy_hub.security import digest_token, token_matches
from tests.conftest import ApiHarness


@dataclass(frozen=True)
class SessionSubject:
    """Seeded enrolment subject identifiers and credential."""

    tenant_id: str
    principal_id: str
    membership_id: str
    enrolment_id: str
    raw_enrolment: str
    team_id: str | None


def seed_session_subject(
    api_harness: ApiHarness,
    *,
    with_team: bool = False,
    scopes: list[str] | None = None,
) -> SessionSubject:
    """Create one active subject with an unconsumed enrolment."""
    tenant_id = new_id("tenant")
    principal_id = new_id("principal")
    membership_id = new_id("membership")
    enrolment_id = new_id("enrol")
    team_id = new_id("team") if with_team else None
    raw_enrolment = f"enrolment-{enrolment_id}"
    with Session(api_harness.engine) as session:
        session.add(Tenant(id=tenant_id, slug=tenant_id, name="Tenant"))
        session.add(
            Principal(
                id=principal_id,
                issuer="https://identity.test",
                subject=principal_id,
            )
        )
        if team_id is not None:
            session.add(
                Team(
                    id=team_id,
                    tenant_id=tenant_id,
                    name="Researchers",
                )
            )
        session.add(
            Membership(
                id=membership_id,
                tenant_id=tenant_id,
                team_id=team_id,
                principal_id=principal_id,
            )
        )
        session.add(
            EnrolmentToken(
                id=enrolment_id,
                token_digest=digest_token(raw_enrolment),
                principal_id=principal_id,
                tenant_id=tenant_id,
                requested_scopes=scopes or ["scholar_info", "scholar_search"],
                expires_at=utc_now() + timedelta(hours=1),
                created_by_principal_id=api_harness.principal_id,
            )
        )
        session.commit()
    return SessionSubject(
        tenant_id=tenant_id,
        principal_id=principal_id,
        membership_id=membership_id,
        enrolment_id=enrolment_id,
        raw_enrolment=raw_enrolment,
        team_id=team_id,
    )


def exchange_session(
    api_harness: ApiHarness,
    subject: SessionSubject,
) -> object:
    """Exchange a seeded enrolment through the public route."""
    return api_harness.client.post(
        "/v1/session",
        json={
            "enrolment_token": subject.raw_enrolment,
            "session_label": "research workstation",
        },
    )


def test_enrolment_exchange_returns_secret_once_and_persists_only_digest(
    api_harness: ApiHarness,
) -> None:
    subject = seed_session_subject(api_harness)
    now = utc_now()
    with Session(api_harness.engine) as session:
        session.add(
            QuotaPolicy(
                tenant_id=subject.tenant_id,
                quota_class="standard",
                request_limit=10,
                period_seconds=3600,
            )
        )
        session.add(
            QuotaWindow(
                tenant_id=subject.tenant_id,
                window_start=quota_window_start(now, 3600),
                period_seconds=3600,
                reserved_count=3,
            )
        )
        session.commit()

    created = exchange_session(api_harness, subject)
    replay = exchange_session(api_harness, subject)

    assert created.status_code == 201
    assert created.headers["cache-control"] == "no-store"
    assert created.headers["pragma"] == "no-cache"
    body = created.json()
    raw_capability = body["session_token"]
    assert raw_capability
    assert body["subject"] == {"user_id": subject.principal_id}
    assert body["tenant"] == {"tenant_id": subject.tenant_id}
    assert body["scopes"] == ["scholar_info", "scholar_search"]
    assert body["quota"] == {"class": "standard", "remaining": 7}

    assert replay.status_code == 401
    assert replay.json()["error"]["code"] == "invalid_credential"
    with Session(api_harness.engine) as session:
        enrolment = session.get(EnrolmentToken, subject.enrolment_id)
        assert enrolment is not None
        assert enrolment.consumed_at is not None
        assert enrolment.version == 2
        capability = session.scalar(
            select(DshCapability).where(
                DshCapability.issued_from_enrolment_id == subject.enrolment_id
            )
        )
        assert capability is not None
        assert capability.token_digest != raw_capability
        assert token_matches(raw_capability, capability.token_digest)
        assert capability.session_label == "research workstation"
        assert capability.expires_at > capability.created_at
        audit = session.scalar(
            select(AuditEvent).where(
                AuditEvent.action == "session:create",
                AuditEvent.outcome == "accepted",
            )
        )
        assert audit is not None
        assert audit.capability_id == capability.id
        assert audit.details == {
            "authentication_method": "enrolment",
            "enrolment_id": subject.enrolment_id,
            "scope_count": 2,
        }
        assert raw_capability not in str(audit.details)
        assert subject.raw_enrolment not in str(audit.details)
        capability_count = session.scalar(
            select(func.count()).select_from(DshCapability)
        )
        audit_count = session.scalar(
            select(func.count())
            .select_from(AuditEvent)
            .where(
                AuditEvent.action == "session:create",
                AuditEvent.outcome == "accepted",
            )
        )
        assert capability_count == 1
        assert audit_count == 1
        denied_audit = session.scalar(
            select(AuditEvent).where(
                AuditEvent.action == "session:create",
                AuditEvent.outcome == "rejected",
            )
        )
        assert denied_audit is not None
        assert denied_audit.details["reason"] == "credential_unavailable"
        assert raw_capability not in str(denied_audit.details)
        assert subject.raw_enrolment not in str(denied_audit.details)

        context = authenticate_capability(
            session,
            f"Bearer {raw_capability}",
        )
        assert context.capability_id == capability.id
        assert context.principal_id == subject.principal_id
        assert context.tenant_id == subject.tenant_id
        assert context.scopes == ("scholar_info", "scholar_search")


def test_enrolment_exchange_reports_unconfigured_quota(
    api_harness: ApiHarness,
) -> None:
    subject = seed_session_subject(api_harness)

    created = exchange_session(api_harness, subject)

    assert created.status_code == 201
    assert created.json()["quota"] == {
        "class": "unconfigured",
        "remaining": None,
    }


@pytest.mark.parametrize("credential_state", ["expired", "revoked", "consumed"])
def test_unavailable_enrolment_states_share_one_credential_error(
    api_harness: ApiHarness,
    credential_state: str,
) -> None:
    subject = seed_session_subject(api_harness)
    with Session(api_harness.engine) as session:
        enrolment = session.get(EnrolmentToken, subject.enrolment_id)
        assert enrolment is not None
        if credential_state == "expired":
            enrolment.expires_at = utc_now() - timedelta(seconds=1)
        elif credential_state == "revoked":
            enrolment.revoked_at = utc_now()
        else:
            enrolment.consumed_at = utc_now()
        session.commit()

    response = exchange_session(api_harness, subject)

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "invalid_credential"
    with Session(api_harness.engine) as session:
        assert session.scalar(select(func.count()).select_from(DshCapability)) == 0


@pytest.mark.parametrize(
    "inactive_resource",
    ["principal", "tenant", "membership", "team"],
)
def test_inactive_subject_state_denies_without_consuming_enrolment(
    api_harness: ApiHarness,
    inactive_resource: str,
) -> None:
    subject = seed_session_subject(
        api_harness,
        with_team=inactive_resource == "team",
    )
    with Session(api_harness.engine) as session:
        if inactive_resource == "principal":
            resource = session.get(Principal, subject.principal_id)
        elif inactive_resource == "tenant":
            resource = session.get(Tenant, subject.tenant_id)
        elif inactive_resource == "membership":
            resource = session.get(Membership, subject.membership_id)
        else:
            assert subject.team_id is not None
            resource = session.get(Team, subject.team_id)
        assert resource is not None
        resource.status = "disabled"
        session.commit()

    response = exchange_session(api_harness, subject)

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "session_denied"
    with Session(api_harness.engine) as session:
        enrolment = session.get(EnrolmentToken, subject.enrolment_id)
        assert enrolment is not None
        assert enrolment.consumed_at is None
        assert session.scalar(select(func.count()).select_from(DshCapability)) == 0


def test_corrupted_scope_assignment_fails_closed_without_consumption(
    api_harness: ApiHarness,
) -> None:
    subject = seed_session_subject(
        api_harness,
        scopes=["scholar_search", "unknown_tool"],
    )

    response = exchange_session(api_harness, subject)

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "session_denied"
    with Session(api_harness.engine) as session:
        enrolment = session.get(EnrolmentToken, subject.enrolment_id)
        assert enrolment is not None
        assert enrolment.consumed_at is None


@pytest.mark.parametrize(
    "inactive_resource",
    ["principal", "tenant", "membership", "team"],
)
def test_capability_authentication_rejects_credentials_and_lost_access(
    api_harness: ApiHarness,
    inactive_resource: str,
) -> None:
    subject = seed_session_subject(
        api_harness,
        with_team=inactive_resource == "team",
    )
    created = exchange_session(api_harness, subject)
    assert created.status_code == 201
    raw_capability = created.json()["session_token"]

    with Session(api_harness.engine) as session:
        for authorization in (
            None,
            "",
            "Basic credential",
            "Bearer",
            "Bearer ",
            "Bearer unknown",
            f"Bearer  {raw_capability}",
            f"Bearer {'x' * 513}",
        ):
            with pytest.raises(HubError) as error:
                authenticate_capability(session, authorization)
            assert error.value.status_code == 401
            assert error.value.code == "invalid_credential"

        valid_context = authenticate_capability(
            session,
            f"bearer {raw_capability}",
        )
        assert valid_context.principal_id == subject.principal_id
        if inactive_resource == "principal":
            resource = session.get(Principal, subject.principal_id)
        elif inactive_resource == "tenant":
            resource = session.get(Tenant, subject.tenant_id)
        elif inactive_resource == "membership":
            resource = session.get(Membership, subject.membership_id)
        else:
            assert subject.team_id is not None
            resource = session.get(Team, subject.team_id)
        assert resource is not None
        resource.status = "disabled"
        session.commit()
        with pytest.raises(HubError) as error:
            authenticate_capability(session, f"Bearer {raw_capability}")
        assert error.value.status_code == 403
        assert error.value.code == "capability_denied"


@pytest.mark.parametrize("scopes", [[], ["unknown_tool"]])
def test_corrupted_capability_scopes_fail_closed(
    api_harness: ApiHarness,
    scopes: list[str],
) -> None:
    subject = seed_session_subject(api_harness)
    created = exchange_session(api_harness, subject)
    assert created.status_code == 201
    raw_capability = created.json()["session_token"]

    with Session(api_harness.engine) as session:
        capability = session.scalar(select(DshCapability))
        assert capability is not None
        capability.scopes = scopes
        session.commit()
        with pytest.raises(HubError) as error:
            authenticate_capability(session, f"Bearer {raw_capability}")
        assert error.value.status_code == 403
        assert error.value.code == "capability_denied"


@pytest.mark.parametrize("capability_state", ["expired", "revoked"])
def test_expired_and_revoked_capabilities_are_invalid_credentials(
    api_harness: ApiHarness,
    capability_state: str,
) -> None:
    subject = seed_session_subject(api_harness)
    created = exchange_session(api_harness, subject)
    assert created.status_code == 201
    raw_capability = created.json()["session_token"]

    with Session(api_harness.engine) as session:
        capability = session.scalar(select(DshCapability))
        assert capability is not None
        if capability_state == "expired":
            capability.expires_at = utc_now() - timedelta(seconds=1)
        else:
            capability.revoked_at = utc_now()
        session.commit()
        with pytest.raises(HubError) as error:
            authenticate_capability(session, f"Bearer {raw_capability}")
        assert error.value.status_code == 401
        assert error.value.code == "invalid_credential"
