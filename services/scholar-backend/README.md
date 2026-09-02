# Scholar backend

The Scholar backend is the academic data plane. It hosts the fixed MCP tool surface and owns one configured corpus, its parsed documents, graph, vectors, embedding integration, and database access.

Runtime entry point: `python -m scholar_mcp`.

Deployment assets: `infra/scholar/`.

The current service accepts the configured direct Phase One credential. A Hub cohort will use a dedicated backend service credential during Phase Two cutover. Scholar does not resolve users, teams, tenants, quotas, or client entitlements.
