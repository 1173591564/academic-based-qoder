# Proxy Hub

This directory reserves the Phase Two control-plane deployable. Runtime code is intentionally not present until the Scholar backend prerequisites and interface decisions in `docs/proxy-hub.md` are complete.

The Hub will own user/session authentication, team-to-tenant resolution, tool policy, quotas, backend routing with MCP session affinity, backend credential brokerage, and append-only audit attribution.

The Hub will not own corpus parsing, graph or vector queries, embeddings, research workflows, or the DSH user interface.
