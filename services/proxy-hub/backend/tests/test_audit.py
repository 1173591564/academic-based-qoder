"""Audit construction and data-minimization tests."""

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from proxy_hub.audit import AuditEntry, append_audit_event, digest_arguments
from proxy_hub.models import AuditEvent, Base


def test_argument_digest_is_stable_without_retaining_payload() -> None:
    first = digest_arguments({"query": "private question", "limit": 3})
    second = digest_arguments({"limit": 3, "query": "private question"})

    assert first == second
    assert "private question" not in first


def test_append_audit_event_records_gateway_dimensions() -> None:
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        append_audit_event(
            session,
            AuditEntry(
                request_id="req_test",
                principal_id="principal_test",
                tenant_id="tenant_test",
                capability_id="cap_test",
                mcp_session_digest="session_digest",
                action="mcp:call",
                resource_type="scholar_tool",
                resource_id="scholar_search",
                outcome="accepted",
                tool_name="scholar_search",
                argument_digest="argument_digest",
                backend_id="backend_test",
                corpus_version="corpus-v1",
                decision="permit",
                latency_ms=12,
                result_class="success",
                returned_bytes=128,
                quota_delta=1,
            ),
        )
        session.commit()

        event = session.scalar(select(AuditEvent))

    assert event is not None
    assert event.tool_name == "scholar_search"
    assert event.backend_id == "backend_test"
    assert event.quota_delta == 1
    engine.dispose()
