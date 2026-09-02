# Proxy Hub Minimum Interface

Proxy Hub is a backend control-plane service in this repository. It authenticates users, resolves their tenant, enforces policy, routes MCP traffic to a Scholar backend, and records attribution. It does not contain research or corpus logic.

## Public API

### `POST /v1/session`

Authenticates an operator-issued enrolment token or an approved identity-provider token and returns a short-lived session capability.

```json
{
  "session_token": "<opaque-or-signed-capability>",
  "expires_at": "2026-09-02T15:00:00Z",
  "subject": { "user_id": "user-..." },
  "tenant": { "tenant_id": "tenant-..." },
  "scopes": ["scholar_search", "scholar_info"],
  "quota": { "class": "standard", "remaining": 1000 }
}
```

Membership resolution happens only on this route. The client stores one credential reference for the returned capability and resolves it per request.

### `POST /v1/mcp/scholar`

Accepts Streamable HTTP MCP traffic authenticated with the session capability.

```text
verify capability
→ resolve tenant
→ authorize exact tool name
→ reserve quota when enabled
→ select a healthy backend with MCP session affinity
→ forward JSON-RPC frames without rewriting
→ append one audit record
```

The Hub must not add model-visible tools, redirect requests, expose backend credentials, or return data from a different tenant when routing information is missing.

## Internal interfaces

```text
decide(principal, tenant, tool) -> permit | deny(reason)
append(audit_record) -> committed | unavailable
resolve_backend(tenant, mcp_session_id) -> backend
```

These are in-process interfaces for the first implementation. They can become separate policy or audit services only when operating requirements justify another deployable component.

## Audit record

Each authorization decision and forwarded tool call records:

- timestamp;
- principal and tenant identifiers;
- session and capability identifiers without token material;
- tool name and argument digest;
- corpus version and selected backend;
- decision, latency, result class, and returned byte count;
- quota delta when quotas are enabled.

Raw research questions are not stored by default.

## Failure behavior

- Missing, invalid, expired, or revoked credentials return `401` without backend contact.
- Unknown or unauthorized tenants and tools return `403`.
- Unknown tenant routing never falls back to a default corpus.
- Policy evaluation failure denies the request.
- Backend unavailability fails the MCP request; DSH startup remains fail closed when initial synchronization cannot complete.
- Audit failure rejects write-capable tools. Read-tool behavior requires an explicit product decision before implementation.
- Public routes never redirect.

## Private administration

The Hub exposes private liveness and readiness. Readiness requires at least one healthy Scholar backend for every tenant currently eligible for routing. Scholar exposes its own private readiness with corpus version, parsed-paper count, vector/chunk counts, graph build timestamp, and synchronization timestamp.

## Deferred capabilities

Team administration CRUD, delegation, impersonation, OAuth UI, billing, per-document ACLs, Memory proxying, response caching, tool rewriting, and Hub-specific MCP tools are not part of the first implementation.
