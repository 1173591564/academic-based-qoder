"""Tenant subject eligibility checks shared by DSH credential flows."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from proxy_hub.models import Membership, Team


def active_membership_exists(
    session: Session,
    principal_id: str,
    tenant_id: str,
) -> bool:
    """Return whether a principal has an active usable tenant membership."""
    memberships = session.scalars(
        select(Membership).where(
            Membership.principal_id == principal_id,
            Membership.tenant_id == tenant_id,
            Membership.status == "active",
        )
    ).all()
    for membership in memberships:
        if membership.team_id is None:
            return True
        team = session.scalar(
            select(Team).where(
                Team.id == membership.team_id,
                Team.tenant_id == tenant_id,
                Team.status == "active",
            )
        )
        if team is not None:
            return True
    return False
