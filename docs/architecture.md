# Scholar Academic Platform Architecture

## Repository boundary

The academic product is split across two repositories rather than duplicated into `frontend/` and `backend/` folders inside one repository.

```text
deepseek-harness                         academic-based-qoder
distributed user client                 server product
├── agent and session runtime            ├── scholar/             academic data plane
├── academic workflows and skills        ├── scholar_mcp/         MCP adapter and transport
├── academic plugins and dashboard       ├── services/            Scholar and Proxy Hub services
├── MCP client and credential refs       ├── infra/               server deployment
└── no corpus or admin policy            └── docs/                architecture and APIs
```

DeepSeek Harness is the independently distributed user client, not the server product's web frontend. Its academic mode packages the user-facing academic workflows, skills, plugins, local dashboard, and MCP integration. This repository owns the server product, including the Scholar data plane, Proxy Hub backend, and separate Proxy Hub administration frontend used by operators.

### Source and generated assets

Runtime source is divided by product boundary: `scholar/` contains academic domain code, `scholar_mcp/` contains the protocol adapter, and `services/proxy-hub/` contains the independently deployable control plane and console. Repository-wide checks are exposed from the root `Makefile`, while each nested service keeps its own build metadata.

Shared IDE content has one authoring location: `.scholar/`. The `.qoder/` and `.claude/` directories are generated tool-specific projections. `scholar/templates/` is the packaged mirror used outside a source checkout and also contains package-only DSH templates. `scripts/sync-ide-config.py` generates and verifies these projections.

## Current Phase One

```text
DSH client
  ├── local academic skills
  ├── agent/session/prompt composition
  ├── local dashboard
  └── credentialed MCP client
          │ Streamable HTTP or stdio
          ▼
Scholar MCP backend
  ├── 16 model-facing tools
  ├── corpus and parsed papers
  ├── graph and vector retrieval
  └── embedding and database access
```

The direct authenticated DSH-to-Scholar route remains supported. Scholar startup and tool synchronization fail closed, HTTP authentication is mandatory except for explicitly enabled loopback development, and clients never receive corpus files or backend provider credentials.

## Target Phase Two

```text
DSH client                              Operator browser
  │ session capability                   │ secure browser session
  │                                      ▼
  │                              Proxy Hub admin console
  │                                      │ /v1/admin/*
  └──────────────────┬───────────────────┘
                     ▼
              Proxy Hub API
              ├── principal authentication
              ├── team and tenant membership
              ├── corpus and tool policy
              ├── quota enforcement
              ├── backend routing and session affinity
              └── append-only audit attribution
                     │ Scholar service credential
                     ▼
              Scholar backend pool
              ├── one corpus boundary per backend process
              ├── immutable corpus version
              ├── parsed papers, graph, vectors, and embeddings
              └── private health and readiness interface
```

Proxy Hub is the control plane owner and the request-path policy enforcement point. Its same-origin administration console manages that control plane but never contacts Scholar directly. Scholar remains the academic data plane. DSH does not implement team authorization, quota counters, audit storage, backend routing, or administration pages.

Proxy Hub has three separately authorized surfaces:

- DSH session and MCP routes under `/v1/session` and `/v1/mcp/`;
- browser administration pages under `/console/` and JSON APIs under `/v1/admin/`;
- private health, metrics, and migration operations that are not internet-facing.

## Backend module ownership

| Module | Owns | Must not own |
| --- | --- | --- |
| `scholar/` | Research workflows, corpus access, parsing, metadata, graph and vector operations, CLI use cases | HTTP authentication, tenant membership, client UI |
| `scholar_mcp/` | The fixed MCP tool presentation, bounded model-facing responses, stdio/HTTP hosting, service authentication | Team policy, quotas, corpus builds |
| `services/scholar-backend/` | Scholar backend deployable definition and operating contract | Proxy Hub policy |
| `services/proxy-hub/backend/` | Phase Two identity, policy, quota, routing, audit, and administration APIs | Research logic, direct Scholar database queries, frontend rendering |
| `services/proxy-hub/frontend/` | Operator administration console and typed use of `/v1/admin/` | DSH research UI, direct Scholar access, authorization decisions |
| `infra/scholar/` | Scholar database and backend deployment assets | Hub identity and audit stores |
| `infra/proxy-hub/` | Hub deployment, ingress, control-plane database, secret references, and audit dependencies | Corpus schema and index builds |

## Isolation and data rules

- A Scholar backend process serves one tenant corpus boundary. Phase Two does not add tenant columns to every Scholar table or pass tenant context through all 16 tools.
- Corpus versions are immutable for a running backend. A rebuild produces a new version and deployment; routing changes only after readiness succeeds.
- Proxy Hub forwards MCP requests without renaming tools or interpreting corpus data.
- The browser console calls only the Hub administration API and cannot use DSH capabilities or Scholar service credentials.
- Backend service credentials are never sent to DSH clients.
- Browser sessions, DSH session capabilities, and backend service credentials are three different credential classes.
- Write or shared-output tools are denied for shared backends until per-user output storage is explicitly designed.

## Migration order

1. Separate MCP tool presentation from transport and process hosting without changing the 16-tool API.
2. Separate Scholar and Proxy Hub deployment directories and document their owners.
3. Add corpus versioning, migrations, private readiness, backup, and restore to Scholar.
4. Scaffold the Proxy Hub backend, control-plane database, and browser-session authentication.
5. Implement tenant, membership, backend-routing, policy, and audit administration pages.
6. Implement the minimal DSH session and MCP routes.
7. Cut over one DSH cohort by changing only its remote URL and credential reference.
8. Enable quotas after audit data establishes useful quota classes.

## Non-goals

- Moving DSH packages into this repository.
- Adding Proxy Hub code to DeepSeek Harness.
- Making a single Scholar process internally multi-tenant.
- Adding billing, a custom identity-provider UI, delegation, impersonation, per-document ACLs, or response caching in the first Hub release.
- Removing the direct Phase One path before the Hub has a tested rollback route.
