"""Control-plane persistence invariant tests."""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from proxy_hub.models import AuditEvent, Base, new_id


def test_audit_events_are_append_only() -> None:
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        event = AuditEvent(
            id=new_id("audit"),
            request_id="req_test",
            principal_id=None,
            tenant_id=None,
            action="test",
            resource_type="test",
            resource_id=None,
            outcome="accepted",
        )
        session.add(event)
        session.commit()
        event.outcome = "changed"
        with pytest.raises(RuntimeError, match="append-only"):
            session.commit()
