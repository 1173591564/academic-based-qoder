"""Single-lab Token facade integration tests."""

from datetime import timedelta

from conftest import ApiHarness
from sqlalchemy import select
from sqlalchemy.orm import Session

from proxy_hub.models import (
    AccessKey,
    AuditEvent,
    Membership,
    Principal,
    ScholarBackend,
    Tenant,
    TenantRoute,
    new_id,
    utc_now,
)
from proxy_hub.security import digest_token


def create_token(
    api_harness: ApiHarness,
    name: str = "Research laptop",
    *,
    idempotency_key: str = "token-create",
) -> tuple[dict[str, object], str]:
    """Create one facade Token and return its one-time value."""
    response = api_harness.client.post(
        "/v1/admin/tokens",
        json={"name": name},
        headers={
            **api_harness.mutation_headers,
            "Idempotency-Key": idempotency_key,
        },
    )
    assert response.status_code == 201
    body = response.json()
    token = body["token"]
    assert isinstance(token, str)
    return body, token


def configure_ready_backend(api_harness: ApiHarness) -> str:
    """Attach a fresh active Scholar Backend to the bootstrapped tenant."""
    with Session(api_harness.engine) as session:
        tenant = session.scalar(select(Tenant))
        assert tenant is not None
        backend = ScholarBackend(
            id=new_id("backend"),
            name="Scholar",
            base_url="http://scholar.test/mcp",
            corpus_version="corpus-v1",
            credential_ref="env:SCHOLAR_TEST_TOKEN",
            status="active",
            capacity={"workspace_isolation": "tenant"},
            last_probe_at=utc_now(),
            last_probe_ready=True,
            last_probe_reason="ready",
        )
        session.add(backend)
        session.add(
            TenantRoute(
                tenant_id=tenant.id,
                backend_id=backend.id,
                corpus_version=backend.corpus_version,
                status="active",
            )
        )
        session.commit()
        return backend.id


def test_create_lists_permanent_digest_only_token(api_harness: ApiHarness) -> None:
    body, token = create_token(api_harness, "  Research laptop  ")

    assert body["name"] == "Research laptop"
    assert body["expires_at"] is None
    assert body["status"] == "active"
    assert body["token_prefix"] == token[:24]
    assert body["token_last_four"] == token[-4:]
    assert "principal_id" not in body
    assert "tenant_id" not in body
    assert "allowed_tools" not in body

    replay = api_harness.client.post(
        "/v1/admin/tokens",
        json={"name": "Research laptop"},
        headers={
            **api_harness.mutation_headers,
            "Idempotency-Key": "token-create",
        },
    )
    listing = api_harness.client.get("/v1/admin/tokens")

    assert replay.status_code == 201
    assert replay.json()["token"] is None
    assert replay.headers["Idempotent-Replayed"] == "true"
    assert listing.json()["items"][0]["token"] is None
    with Session(api_harness.engine) as session:
        access_key = session.scalar(select(AccessKey))
        principal = session.scalar(
            select(Principal).where(Principal.kind == "managed_researcher")
        )
        assert access_key is not None
        assert principal is not None
        assert access_key.token_digest == digest_token(token)
        assert token not in str(access_key.__dict__)
        assert access_key.expires_at is None
        assert len(access_key.allowed_tools) == 16
        assert principal.managed_name_key == "research laptop"


def test_token_name_is_unicode_casefold_unique(api_harness: ApiHarness) -> None:
    create_token(api_harness, "Ａlice")

    duplicate = api_harness.client.post(
        "/v1/admin/tokens",
        json={"name": "alice"},
        headers={
            **api_harness.mutation_headers,
            "Idempotency-Key": "duplicate-name",
        },
    )

    assert duplicate.status_code == 409
    assert duplicate.json()["error"]["code"] == "token_name_conflict"


def test_rename_rotate_revoke_and_delete_token(api_harness: ApiHarness) -> None:
    configure_ready_backend(api_harness)
    body, old_token = create_token(api_harness)

    renamed = api_harness.client.patch(
        f"/v1/admin/tokens/{body['id']}",
        json={"name": "Literature group"},
        headers={
            **api_harness.mutation_headers,
            "If-Match": body["etag"],
        },
    )
    assert renamed.status_code == 200
    assert renamed.json()["name"] == "Literature group"

    rotated = api_harness.client.post(
        f"/v1/admin/tokens/{body['id']}/rotate",
        json={"confirm": True},
        headers={
            **api_harness.mutation_headers,
            "Idempotency-Key": "rotate-token",
        },
    )
    assert rotated.status_code == 201
    rotated_body = rotated.json()
    new_token = rotated_body["token"]
    assert new_token != old_token
    assert (
        api_harness.client.get(
            "/v1/me",
            headers={"Authorization": f"Bearer {old_token}"},
        ).status_code
        == 401
    )
    me = api_harness.client.get(
        "/v1/me",
        headers={"Authorization": f"Bearer {new_token}"},
    )
    assert me.status_code == 200
    assert me.json() == {
        "name": "Literature group",
        "scholar": {
            "available": True,
            "corpus_version": "corpus-v1",
        },
    }

    revoked = api_harness.client.post(
        f"/v1/admin/tokens/{rotated_body['id']}/revoke",
        headers={
            **api_harness.mutation_headers,
            "If-Match": rotated_body["etag"],
        },
    )
    assert revoked.status_code == 204
    assert (
        api_harness.client.get(
            "/v1/me",
            headers={"Authorization": f"Bearer {new_token}"},
        ).status_code
        == 401
    )

    replacement = api_harness.client.post(
        f"/v1/admin/tokens/{rotated_body['id']}/rotate",
        json={"confirm": True},
        headers={
            **api_harness.mutation_headers,
            "Idempotency-Key": "restore-token",
        },
    )
    assert replacement.status_code == 201
    replacement_body = replacement.json()
    deleted = api_harness.client.delete(
        f"/v1/admin/tokens/{replacement_body['id']}",
        headers={
            **api_harness.mutation_headers,
            "If-Match": replacement_body["etag"],
        },
    )
    assert deleted.status_code == 204
    with Session(api_harness.engine) as session:
        principal = session.scalar(
            select(Principal).where(Principal.managed_name_key == "literature group")
        )
        assert principal is not None
        membership = session.scalar(
            select(Membership).where(
                Membership.principal_id == principal.id,
            )
        )
        assert membership is not None
        assert principal.status == "disabled"
        assert membership.status == "disabled"


def test_me_distinguishes_invalid_token_and_unavailable_backend(
    api_harness: ApiHarness,
) -> None:
    _body, token = create_token(api_harness)

    invalid = api_harness.client.get(
        "/v1/me",
        headers={"Authorization": "Bearer invalid"},
    )
    unavailable = api_harness.client.get(
        "/v1/me",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert invalid.status_code == 401
    assert invalid.json()["error"]["code"] == "invalid_credential"
    assert unavailable.status_code == 503
    assert unavailable.json()["error"]["code"] == "backend_unavailable"


def test_service_status_probe_and_minimized_audit(api_harness: ApiHarness) -> None:
    backend_id = configure_ready_backend(api_harness)
    body, _token = create_token(api_harness)
    with Session(api_harness.engine) as session:
        session.add(
            AuditEvent(
                id=new_id("audit"),
                request_id="request-visible",
                principal_id="internal-principal",
                tenant_id=session.scalar(select(Tenant.id)),
                access_key_id=body["id"],
                action="mcp:tool",
                resource_type="scholar_backend",
                resource_id=backend_id,
                outcome="forwarded",
                tool_name="scholar_search",
                argument_digest="must-not-appear",
                backend_id=backend_id,
                corpus_version="corpus-v1",
                decision="permit",
                latency_ms=12,
                result_class="2xx",
                returned_bytes=100,
                details={"request_body": "must-not-appear"},
            )
        )
        session.commit()

    status = api_harness.client.get("/v1/admin/service-status")
    probed = api_harness.client.post(
        "/v1/admin/service-status/probe",
        headers=api_harness.mutation_headers,
    )
    now = utc_now()
    audit = api_harness.client.get(
        "/v1/admin/token-audit",
        params={
            "from": (now - timedelta(hours=1)).isoformat(),
            "to": (now + timedelta(hours=1)).isoformat(),
        },
    )

    assert status.status_code == 200
    assert status.json()["available"] is True
    assert status.json()["corpus_version"] == "corpus-v1"
    assert probed.status_code == 200
    assert probed.json()["available"] is True
    assert audit.status_code == 200
    assert audit.json()["items"] == [
        {
            "token_name": "Research laptop",
            "mcp_tool": "scholar_search",
            "occurred_at": audit.json()["items"][0]["occurred_at"],
            "result": "forwarded",
            "duration_ms": 12,
            "request_id": "request-visible",
        }
    ]
