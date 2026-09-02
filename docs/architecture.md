# Scholar Academic Platform Architecture

## Repository boundary

The academic product is split across two repositories rather than duplicated into `frontend/` and `backend/` folders inside one repository.

```text
deepseek-harness                         academic-based-qoder
client / user-facing plane              backend / server plane
├── agent and session runtime            ├── scholar/             research engine
├── local dashboard and questions        ├── scholar_mcp/         MCP adapter and transport
├── local skills and prompt assembly     ├── services/            deployable service ownership
├── MCP client and credential refs       ├── infra/               service-specific deployment
└── no corpus or tenant policy           └── docs/                backend architecture and APIs
```

DeepSeek Harness is the frontend/client plane even when its primary interface is a CLI or local dashboard. This repository is the backend workspace. Proxy Hub code, Scholar corpus operations, database migrations, indexes, and server deployment stay here.

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
DSH client
  │ one user/session credential
  ▼
Proxy Hub
  ├── principal authentication
  ├── team and tenant membership
  ├── corpus authorization
  ├── tool policy
  ├── quota enforcement
  ├── backend routing and session affinity
  └── append-only audit attribution
          │ service credential
          ▼
Scholar backend pool
  ├── one corpus boundary per backend process
  ├── immutable corpus version
  ├── parsed papers, graph, vectors, and embeddings
  └── private health and readiness interface
```

Proxy Hub is the control plane owner and the request-path policy enforcement point. Scholar remains the academic data plane. DSH does not implement team authorization, quota counters, audit storage, or backend routing.

## Backend module ownership

| Module | Owns | Must not own |
| --- | --- | --- |
| `scholar/` | Research workflows, corpus access, parsing, metadata, graph and vector operations, CLI use cases | HTTP authentication, tenant membership, client UI |
| `scholar_mcp/` | The fixed MCP tool presentation, bounded model-facing responses, stdio/HTTP hosting, service authentication | Team policy, quotas, corpus builds |
| `services/scholar-backend/` | Scholar backend deployable definition and operating contract | Proxy Hub policy |
| `services/proxy-hub/` | Phase Two control-plane and routing service definition | Research logic, direct database queries, embeddings |
| `infra/scholar/` | Scholar database and backend deployment assets | Hub identity and audit stores |
| `infra/proxy-hub/` | Hub deployment, tenant registry, audit and routing dependencies | Corpus schema and index builds |

## Isolation and data rules

- A Scholar backend process serves one tenant corpus boundary. Phase Two does not add tenant columns to every Scholar table or pass tenant context through all 16 tools.
- Corpus versions are immutable for a running backend. A rebuild produces a new version and deployment; routing changes only after readiness succeeds.
- Proxy Hub forwards MCP requests without renaming tools or interpreting corpus data.
- Backend service credentials are never sent to DSH clients.
- User/session credentials and backend service credentials are different credential classes.
- Write or shared-output tools are denied for shared backends until per-user output storage is explicitly designed.

## Migration order

1. Separate MCP tool presentation from transport and process hosting without changing the 16-tool API.
2. Separate Scholar and Proxy Hub deployment directories and document their owners.
3. Add corpus versioning, migrations, private readiness, backup, and restore to Scholar.
4. Implement the minimal Proxy Hub session and MCP routes.
5. Cut over one DSH cohort by changing only its remote URL and credential reference.
6. Add quotas only after audit data establishes useful quota classes.

## Non-goals

- Moving DSH packages into this repository.
- Adding Proxy Hub code to DeepSeek Harness.
- Making a single Scholar process internally multi-tenant.
- Adding team administration UI, billing, OAuth flows, per-document ACLs, or response caching in the first Hub release.
- Removing the direct Phase One path before the Hub has a tested rollback route.
