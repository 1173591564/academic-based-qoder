# Proxy Hub

This directory contains the first runnable Proxy Hub control-plane slice.

- `backend/` contains the FastAPI administration service, OIDC browser sessions, tenant-scoped RBAC, append-only audit records, SQLAlchemy models, and Alembic migrations.
- `frontend/` contains the React and TypeScript operator console served at `/console/`.

The implemented slice supports operator login, overview health, tenant listing, platform-administrator tenant creation, ETag-protected tenant updates, and explicit loading, empty, denied, and unavailable states. The remaining team, policy, quota, Scholar routing, DSH capability, and MCP gateway surfaces remain defined in `docs/proxy-hub.md` and `docs/proxy-hub-console.md`.

Neither side will own corpus parsing, graph or vector queries, embeddings, research workflows, or the DSH user interface.

Local deployment instructions are in `infra/proxy-hub/README.md`.
