# Proxy Hub

This directory contains the Proxy Hub control plane and Scholar MCP gateway.

- `backend/` contains the FastAPI administration service, OIDC browser sessions, the single-lab Token facade, append-only audit records, SQLAlchemy models, and Alembic migrations.
- `frontend/` contains the React and TypeScript operator console served at `/console/`.

The administrator console exposes Token management, Service status, and Audit log. The single-lab facade initializes one deployment-owned tenant, route, tool policy, managed Principal, and Membership automatically; those compatibility resources are not user-facing. New Tokens are permanent until rotation or revoke, receive the fixed 16-tool Scholar catalog, and do not carry a user quota.

Proxy Hub authenticates each Token, applies global request protections, selects the Scholar Backend, injects the deployment-owned service credential, and stores minimized audit metadata. It never forwards a user Token or stores research request bodies.

Corpus parsing, graph or vector queries, embeddings, research workflows, and the DSH user interface remain outside Proxy Hub.

Local deployment instructions are in `infra/proxy-hub/README.md`.
