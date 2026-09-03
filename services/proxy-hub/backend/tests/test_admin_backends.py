"""Backend registry, tenant policy, and route administration tests."""

from datetime import timedelta

from conftest import ApiHarness
from sqlalchemy import select
from sqlalchemy.orm import Session

from proxy_hub.models import (
    AuditEvent,
    BrowserSession,
    Membership,
    Principal,
    RoleBinding,
    ScholarBackend,
    new_id,
    utc_now,
)
from proxy_hub.rbac import OPERATOR
from proxy_hub.security import digest_token


def create_tenant(harness: ApiHarness, slug: str = "routing-tenant") -> str:
    response = harness.client.post(
        "/v1/admin/tenants",
        json={"slug": slug, "name": "Routing Tenant"},
        headers={
            **harness.mutation_headers,
            "Idempotency-Key": f"tenant-{slug}",
        },
    )
    assert response.status_code == 201
    return str(response.json()["id"])


def create_backend(
    harness: ApiHarness,
    *,
    name: str = "Scholar Primary",
    idempotency_key: str = "backend-primary",
) -> tuple[str, str]:
    response = harness.client.post(
        "/v1/admin/backends",
        json={
            "name": name,
            "base_url": "http://scholar.test/mcp",
            "corpus_version": "corpus-v1",
            "credential_ref": "env:SCHOLAR_TEST_TOKEN",
            "credential_version": "version-1",
        },
        headers={
            **harness.mutation_headers,
            "Idempotency-Key": idempotency_key,
        },
    )
    assert response.status_code == 201
    assert "credential_ref" not in response.json()
    assert response.json()["credential"] == {
        "configured": True,
        "version": "version-1",
        "rotated_at": response.json()["credential"]["rotated_at"],
    }
    return str(response.json()["id"]), response.headers["etag"]


def test_backend_registration_probe_activation_and_route(
    api_harness: ApiHarness,
) -> None:
    tenant_id = create_tenant(api_harness)
    backend_id, create_etag = create_backend(api_harness)

    replay = api_harness.client.post(
        "/v1/admin/backends",
        json={
            "name": "Scholar Primary",
            "base_url": "http://scholar.test/mcp",
            "corpus_version": "corpus-v1",
            "credential_ref": "env:SCHOLAR_TEST_TOKEN",
            "credential_version": "version-1",
        },
        headers={
            **api_harness.mutation_headers,
            "Idempotency-Key": "backend-primary",
        },
    )
    assert replay.status_code == 201
    assert replay.headers["idempotent-replayed"] == "true"
    assert replay.headers["etag"] == create_etag
    assert "credential_ref" not in replay.json()

    probe = api_harness.client.post(
        f"/v1/admin/backends/{backend_id}:probe",
        headers=api_harness.mutation_headers,
    )
    assert probe.status_code == 200
    assert probe.json()["probe"]["ready"] is True
    assert probe.json()["probe"]["reason"] == "ready"
    assert probe.json()["capacity"]["workspace_isolation"] == "tenant"
    assert probe.json()["capacity"]["parsed_papers"] == 12

    activated = api_harness.client.patch(
        f"/v1/admin/backends/{backend_id}",
        json={"status": "active"},
        headers={
            **api_harness.mutation_headers,
            "If-Match": probe.headers["etag"],
        },
    )
    assert activated.status_code == 200
    assert activated.json()["status"] == "active"

    route = api_harness.client.put(
        f"/v1/admin/tenants/{tenant_id}/backend-route",
        json={
            "backend_id": backend_id,
            "corpus_version": "corpus-v1",
            "status": "active",
        },
        headers={**api_harness.mutation_headers, "If-Match": "*"},
    )
    assert route.status_code == 201
    assert route.json()["backend_id"] == backend_id
    assert route.json()["corpus_version"] == "corpus-v1"

    listed = api_harness.client.get("/v1/admin/backends")
    assert listed.status_code == 200
    assert [item["id"] for item in listed.json()["items"]] == [backend_id]
    assert "credential_ref" not in listed.json()["items"][0]


def test_backend_activation_requires_current_successful_probe(
    api_harness: ApiHarness,
) -> None:
    backend_id, etag = create_backend(api_harness)
    activation = api_harness.client.patch(
        f"/v1/admin/backends/{backend_id}",
        json={"status": "active"},
        headers={**api_harness.mutation_headers, "If-Match": etag},
    )
    assert activation.status_code == 409
    assert activation.json()["error"]["code"] == "backend_probe_required"

    invalid_url = api_harness.client.post(
        "/v1/admin/backends",
        json={
            "name": "Unsafe backend",
            "base_url": "https://user:password@scholar.test/mcp",
            "corpus_version": "corpus-v1",
            "credential_ref": "env:SCHOLAR_TEST_TOKEN",
        },
        headers={
            **api_harness.mutation_headers,
            "Idempotency-Key": "unsafe-backend",
        },
    )
    assert invalid_url.status_code == 400
    assert invalid_url.json()["error"]["code"] == "backend_url_invalid"


def test_credential_rotation_invalidates_readiness_without_exposure(
    api_harness: ApiHarness,
    monkeypatch,
) -> None:
    monkeypatch.setenv("SCHOLAR_ROTATED_TOKEN", "rotated-service-token")
    backend_id, _etag = create_backend(api_harness)
    probe = api_harness.client.post(
        f"/v1/admin/backends/{backend_id}:probe",
        headers=api_harness.mutation_headers,
    )
    rotation = api_harness.client.post(
        f"/v1/admin/backends/{backend_id}:rotate-credential",
        json={
            "credential_ref": "env:SCHOLAR_ROTATED_TOKEN",
            "credential_version": "version-2",
        },
        headers={
            **api_harness.mutation_headers,
            "If-Match": probe.headers["etag"],
        },
    )
    assert rotation.status_code == 200
    assert rotation.json()["credential"]["version"] == "version-2"
    assert rotation.json()["probe"]["ready"] is False
    assert rotation.json()["probe"]["reason"] == "credential_rotated"
    assert "credential_ref" not in rotation.json()

    with Session(api_harness.engine) as session:
        backend = session.get(ScholarBackend, backend_id)
        assert backend is not None
        assert backend.credential_ref == "env:SCHOLAR_ROTATED_TOKEN"
        audit_details = list(
            session.scalars(
                select(AuditEvent.details).where(
                    AuditEvent.action == "backend:rotate_credential"
                )
            ).all()
        )
    assert len(audit_details) == 1
    assert "SCHOLAR_ROTATED_TOKEN" not in str(audit_details[0])
    assert "rotated-service-token" not in str(audit_details[0])


def test_tool_and_quota_policy_upsert_with_etags(
    api_harness: ApiHarness,
) -> None:
    tenant_id = create_tenant(api_harness, "policy-tenant")
    tool_policy = api_harness.client.put(
        f"/v1/admin/tenants/{tenant_id}/tool-policy",
        json={"allowed_tools": ["scholar_info", "scholar_search"]},
        headers={**api_harness.mutation_headers, "If-Match": "*"},
    )
    assert tool_policy.status_code == 201
    assert tool_policy.json()["allowed_tools"] == [
        "scholar_info",
        "scholar_search",
    ]
    updated = api_harness.client.put(
        f"/v1/admin/tenants/{tenant_id}/tool-policy",
        json={"allowed_tools": ["scholar_info"]},
        headers={
            **api_harness.mutation_headers,
            "If-Match": tool_policy.headers["etag"],
        },
    )
    assert updated.status_code == 200
    stale = api_harness.client.put(
        f"/v1/admin/tenants/{tenant_id}/tool-policy",
        json={"allowed_tools": ["scholar_search"]},
        headers={
            **api_harness.mutation_headers,
            "If-Match": tool_policy.headers["etag"],
        },
    )
    assert stale.status_code == 412

    invalid = api_harness.client.put(
        f"/v1/admin/tenants/{tenant_id}/tool-policy",
        json={"allowed_tools": ["proxy_hub_admin"]},
        headers={
            **api_harness.mutation_headers,
            "If-Match": updated.headers["etag"],
        },
    )
    assert invalid.status_code == 400
    assert invalid.json()["error"]["code"] == "tool_policy_invalid"

    quota = api_harness.client.put(
        f"/v1/admin/tenants/{tenant_id}/quota-policy",
        json={
            "quota_class": "research",
            "request_limit": 100,
            "period_seconds": 3600,
            "concurrency_limit": 4,
            "enforcement_enabled": True,
        },
        headers={**api_harness.mutation_headers, "If-Match": "*"},
    )
    assert quota.status_code == 201
    assert quota.json()["request_limit"] == 100
    assert quota.json()["concurrency_limit"] == 4
    assert quota.json()["enforcement_enabled"] is True


def test_route_rejects_unready_backend_and_wrong_corpus(
    api_harness: ApiHarness,
) -> None:
    tenant_id = create_tenant(api_harness, "closed-route")
    backend_id, _etag = create_backend(api_harness)
    wrong_corpus = api_harness.client.put(
        f"/v1/admin/tenants/{tenant_id}/backend-route",
        json={
            "backend_id": backend_id,
            "corpus_version": "corpus-v2",
            "status": "active",
        },
        headers={**api_harness.mutation_headers, "If-Match": "*"},
    )
    assert wrong_corpus.status_code == 409
    assert wrong_corpus.json()["error"]["code"] == "corpus_version_mismatch"

    unready = api_harness.client.put(
        f"/v1/admin/tenants/{tenant_id}/backend-route",
        json={
            "backend_id": backend_id,
            "corpus_version": "corpus-v1",
            "status": "active",
        },
        headers={**api_harness.mutation_headers, "If-Match": "*"},
    )
    assert unready.status_code == 409
    assert unready.json()["error"]["code"] == "backend_not_ready"


def test_operator_can_only_read_and_probe_routed_backends(
    api_harness: ApiHarness,
) -> None:
    tenant_id = create_tenant(api_harness, "operator-tenant")
    routed_backend_id, _etag = create_backend(api_harness)
    probe = api_harness.client.post(
        f"/v1/admin/backends/{routed_backend_id}:probe",
        headers=api_harness.mutation_headers,
    )
    activated = api_harness.client.patch(
        f"/v1/admin/backends/{routed_backend_id}",
        json={"status": "active"},
        headers={
            **api_harness.mutation_headers,
            "If-Match": probe.headers["etag"],
        },
    )
    assert activated.status_code == 200
    route = api_harness.client.put(
        f"/v1/admin/tenants/{tenant_id}/backend-route",
        json={
            "backend_id": routed_backend_id,
            "corpus_version": "corpus-v1",
            "status": "active",
        },
        headers={**api_harness.mutation_headers, "If-Match": "*"},
    )
    assert route.status_code == 201
    hidden_backend_id, _etag = create_backend(
        api_harness,
        name="Scholar Hidden",
        idempotency_key="backend-hidden",
    )

    raw_session = "operator-session"
    csrf_token = "operator-csrf"
    with Session(api_harness.engine) as session:
        principal_id = new_id("principal")
        session.add(
            Principal(
                id=principal_id,
                issuer="https://identity.test",
                subject="operator",
                email="operator@example.test",
                display_name="Operator",
            )
        )
        session.add(
            Membership(
                id=new_id("membership"),
                tenant_id=tenant_id,
                principal_id=principal_id,
                status="active",
            )
        )
        session.add(
            RoleBinding(
                id=new_id("role"),
                tenant_id=tenant_id,
                principal_id=principal_id,
                role=OPERATOR,
            )
        )
        session.add(
            BrowserSession(
                id=digest_token(raw_session),
                principal_id=principal_id,
                csrf_digest=digest_token(csrf_token),
                expires_at=utc_now() + timedelta(hours=1),
            )
        )
        session.commit()

    api_harness.client.cookies.set("proxy_hub_session", raw_session)
    api_harness.client.cookies.set("proxy_hub_csrf", csrf_token)
    listed = api_harness.client.get("/v1/admin/backends")
    assert listed.status_code == 200
    assert [item["id"] for item in listed.json()["items"]] == [routed_backend_id]
    assert (
        api_harness.client.get(f"/v1/admin/backends/{hidden_backend_id}").status_code
        == 404
    )
    mutation_headers = {
        "Origin": "http://testserver",
        "X-CSRF-Token": csrf_token,
    }
    assert (
        api_harness.client.patch(
            f"/v1/admin/backends/{routed_backend_id}",
            json={"status": "disabled"},
            headers={**mutation_headers, "If-Match": activated.headers["etag"]},
        ).status_code
        == 403
    )
    reprobe = api_harness.client.post(
        f"/v1/admin/backends/{routed_backend_id}:probe",
        headers=mutation_headers,
    )
    assert reprobe.status_code == 200
