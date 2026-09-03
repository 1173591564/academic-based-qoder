# Proxy Hub

This directory contains the first runnable Proxy Hub control-plane slice.

- `backend/` contains the FastAPI administration service, OIDC browser sessions, tenant-scoped RBAC, append-only audit records, SQLAlchemy models, and Alembic migrations.
- `frontend/` contains the React and TypeScript operator console served at `/console/`.

The backend supports operator login, tenant IAM, DSH capabilities, the Scholar
MCP gateway, exact tool policy, quota enforcement, Scholar backend registration
and readiness-gated tenant routes. The current console exposes only the initial
overview and tenant surfaces; the remaining administration pages are defined
in `docs/proxy-hub-console.md`.

Neither side will own corpus parsing, graph or vector queries, embeddings, research workflows, or the DSH user interface.

Local deployment instructions are in `infra/proxy-hub/README.md`.
