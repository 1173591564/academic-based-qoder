# Proxy Hub

This directory reserves the Phase Two control-plane product. Runtime code is intentionally not present until the Scholar backend prerequisites and interface decisions in `docs/proxy-hub.md` and `docs/proxy-hub-console.md` are complete.

- `backend/` will contain the Python ASGI gateway and administration API.
- `frontend/` will contain the TypeScript operator administration console.

The Hub backend will own user/session authentication, team-to-tenant resolution, tool policy, quotas, backend routing with MCP session affinity, backend credential brokerage, and append-only audit attribution. The frontend will manage those resources only through the administration API.

Neither side will own corpus parsing, graph or vector queries, embeddings, research workflows, or the DSH user interface.
