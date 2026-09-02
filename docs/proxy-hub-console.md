# Proxy Hub Management Console Design

## Product surfaces

Proxy Hub includes an operator-facing web application in addition to its DSH gateway. The surfaces share one public origin but use different credentials and authorization policies.

```text
DSH client                           Operator browser
Bearer session capability           HttpOnly browser session
     │                                      │
     ▼                                      ▼
/v1/session, /v1/mcp/*              /console/*, /v1/admin/*
     └──────────────────┬───────────────────┘
                        ▼
                 Proxy Hub backend
                 ├── control-plane PostgreSQL
                 ├── secret-manager references
                 ├── policy and quota evaluation
                 ├── routing and MCP affinity
                 └── append-only audit
                        │ service credential
                        ▼
                 Scholar backend pool
```

The administration frontend never contacts Scholar, the Hub database, or a secret manager directly. It renders Hub API responses and submits operator intent; the backend makes every authorization and state-transition decision.

## Source and deployment layout

```text
services/proxy-hub/
├── backend/     Python ASGI control-plane and gateway
└── frontend/    TypeScript administration SPA
```

The implementation baseline is a FastAPI backend and a React/TypeScript frontend built with Vite. These are separate source and test units. Production ingress serves the compiled console and Hub APIs from one HTTPS origin so normal operation needs no cross-origin browser access.

The first release may package both build outputs into one deployable image or run separate web and API containers behind the same ingress. The external paths and credential separation remain identical in either topology.

## Authentication and authorization

- Console sign-in delegates identity verification to an approved OIDC provider. Proxy Hub owns the callback and server-side session; the browser receives only a `Secure`, `HttpOnly`, `SameSite=Lax` cookie.
- Browser tokens and provider refresh tokens are never stored in local storage or exposed to frontend code.
- Mutating administration requests require same-origin checks and a CSRF token bound to the browser session.
- DSH session capabilities are Bearer credentials accepted only by DSH-facing routes.
- Scholar service credentials are resolved server-side from secret references and are never returned by any API.
- Every route is deny-by-default and checks both role and tenant scope.

### Initial roles

| Role | Scope | Capabilities |
| --- | --- | --- |
| `platform_admin` | all tenants | manage tenants, operators, backend registry, routes, policies, quotas, and retention settings |
| `tenant_admin` | assigned tenants | manage teams, memberships, tool policy, and quota allocation within assigned tenants |
| `operator` | assigned tenants | inspect health and usage and run non-mutating backend probes |
| `auditor` | assigned tenants or global | read audit and usage data without mutation access |

A principal can hold multiple role bindings. Tenant-scoped roles never gain access through a missing or unknown tenant identifier.

## Page information architecture

| Route | Purpose | Primary APIs | Roles |
| --- | --- | --- | --- |
| `/console/` | health, recent failures, usage, and quota summary | `/v1/admin/overview`, `/v1/admin/me` | all |
| `/console/tenants` | tenant lifecycle and corpus assignment | `/v1/admin/tenants` | platform admin |
| `/console/tenants/{id}` | one tenant's status, corpus, and route summary | `/v1/admin/tenants/{id}` | platform admin or assigned tenant roles |
| `/console/tenants/{id}/members` | teams, principals, memberships, and tenant roles | tenant-scoped team and membership APIs | platform or tenant admin |
| `/console/tenants/{id}/policy` | exact Scholar tool allowlist | `/v1/admin/tenants/{id}/tool-policy` | platform or tenant admin |
| `/console/tenants/{id}/quota` | quota class and allocation | `/v1/admin/tenants/{id}/quota-policy` | platform or tenant admin |
| `/console/tenants/{id}/route` | active Scholar backend and readiness | `/v1/admin/tenants/{id}/backend-route` | platform admin or operator |
| `/console/principals` | global principal status and platform roles | `/v1/admin/principals`, `/v1/admin/platform-role-bindings` | platform admin |
| `/console/backends` | Scholar health, corpus versions, and credential rotation | `/v1/admin/backends` | platform admin or operator |
| `/console/audit` | cursor-paginated authorization and mutation records | `/v1/admin/audit-events` | platform admin or auditor |
| `/console/settings` | identity-provider metadata and retention policy | `/v1/admin/settings` | platform admin |

The first usable slice includes sign-in, overview, tenants, teams/memberships, tool policy, backends/routes, and audit. Quota editing and settings follow after request-path audit is reliable.

### Page behavior

- Tenant-scoped pages include the tenant identifier in the URL. A missing tenant never selects a default for a mutation.
- Navigation and action controls derive from the capability list returned by `/v1/admin/me`; hiding a control does not replace backend authorization.
- Policy and routing changes are pessimistic: the page waits for the server response and refreshes the ETag before displaying success.
- Revocation, route replacement, and credential rotation require a confirmation dialog that names the affected tenant or backend.
- Health cards show the observation timestamp and distinguish stale data from a currently failing probe.
- Lists provide explicit loading, empty, denied, and unavailable states. A denied resource is not represented as an empty collection.

## Administration API

### Browser authentication and overview

```text
GET    /auth/login
GET    /auth/callback
GET    /v1/admin/me
POST   /v1/admin/logout
GET    /v1/admin/overview
```

Only the two OIDC handshake routes may redirect, and only to configured allowlisted origins. DSH session and MCP routes never redirect.

### Tenants, teams, and principals

```text
GET    /v1/admin/tenants
POST   /v1/admin/tenants
GET    /v1/admin/tenants/{tenant_id}
PATCH  /v1/admin/tenants/{tenant_id}

GET    /v1/admin/tenants/{tenant_id}/teams
POST   /v1/admin/tenants/{tenant_id}/teams
PATCH  /v1/admin/tenants/{tenant_id}/teams/{team_id}
GET    /v1/admin/tenants/{tenant_id}/memberships
POST   /v1/admin/tenants/{tenant_id}/memberships
PATCH  /v1/admin/tenants/{tenant_id}/memberships/{membership_id}
DELETE /v1/admin/tenants/{tenant_id}/memberships/{membership_id}
GET    /v1/admin/tenants/{tenant_id}/role-bindings
POST   /v1/admin/tenants/{tenant_id}/role-bindings
DELETE /v1/admin/tenants/{tenant_id}/role-bindings/{binding_id}
GET    /v1/admin/principals
PATCH  /v1/admin/principals/{principal_id}
GET    /v1/admin/platform-role-bindings
POST   /v1/admin/platform-role-bindings
DELETE /v1/admin/platform-role-bindings/{binding_id}
```

Delete operations revoke or disable control-plane records; they do not erase audit history.

### Policy and quota

```text
GET    /v1/admin/tenants/{tenant_id}/tool-policy
PUT    /v1/admin/tenants/{tenant_id}/tool-policy
GET    /v1/admin/tenants/{tenant_id}/quota-policy
PUT    /v1/admin/tenants/{tenant_id}/quota-policy
```

Tool policy stores exact names from the frozen Scholar tool catalog. Unknown names fail validation instead of becoming inactive policy entries.

### Scholar backends and routing

```text
GET    /v1/admin/backends
POST   /v1/admin/backends
GET    /v1/admin/backends/{backend_id}
PATCH  /v1/admin/backends/{backend_id}
POST   /v1/admin/backends/{backend_id}:probe
POST   /v1/admin/backends/{backend_id}:rotate-credential
GET    /v1/admin/tenants/{tenant_id}/backend-route
PUT    /v1/admin/tenants/{tenant_id}/backend-route
```

Backend responses expose health, corpus version, capacity metadata, and secret-reference status, never credential values. Credential rotation accepts a new secret reference, not secret material. Route activation requires a successful readiness probe for the requested corpus version.

### Audit and usage

```text
GET    /v1/admin/audit-events
GET    /v1/admin/tenants/{tenant_id}/audit-events
GET    /v1/admin/usage
GET    /v1/admin/tenants/{tenant_id}/usage
GET    /v1/admin/settings
PUT    /v1/admin/settings
```

Audit and usage queries require bounded time ranges and cursor pagination. Raw research questions and Bearer credentials are not queryable fields.

## API behavior

List responses use cursor pagination and stable resource identifiers. Create requests accept an `Idempotency-Key`. Mutations require `If-Match` with the current resource ETag so two operators cannot silently overwrite each other.

```json
{
  "error": {
    "code": "tenant_scope_denied",
    "message": "The requested tenant is not available to this session.",
    "request_id": "req_..."
  }
}
```

- `400` reports malformed input.
- `401` reports an absent or expired browser session.
- `403` reports role or tenant-scope denial.
- `404` hides resources outside the caller's visible scope.
- `409` reports an idempotency or state-transition conflict.
- `412` reports a stale ETag.
- `429` reports an administration rate limit.
- `503` reports an unavailable required dependency.

Every accepted mutation writes an immutable operator audit record through the same transaction or a durable outbox. If that guarantee is unavailable, the mutation fails.

## Control-plane data

The Hub uses a database isolated from Scholar data. Its initial resources are principals, browser sessions, tenants, teams, memberships, role bindings, tool policies, quota policies, Scholar backend registrations, tenant routes, DSH capabilities, and audit events.

Secret values live in a deployment secret manager. Hub records contain only secret references, versions, rotation timestamps, and non-sensitive status.

## Explicitly deferred

Billing, custom identity-provider pages, delegation, impersonation, bulk CSV administration, per-document ACLs, support access to raw research content, cross-tenant dashboards, and a mobile administration UI are not part of the first console release.
