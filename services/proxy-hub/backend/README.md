# Proxy Hub backend

The backend is a Python FastAPI control-plane service. The current route groups are:

- OIDC login and callback routes under `/auth/`;
- DSH enrolment exchange and holder revocation under `/v1/session`;
- authenticated Scholar Streamable HTTP MCP under `/v1/mcp/scholar`;
- browser-session administration APIs under `/v1/admin/`;
- private liveness and readiness routes under `/private/health/`.

It is the only component allowed to read or mutate the Hub control-plane
database, evaluate authorization, or append audit records.
It resolves deployment-owned Scholar credentials only while forwarding an MCP
request; raw DSH capabilities, Scholar credentials, MCP session identifiers,
and research arguments are not persisted in control-plane records.
Each MCP tool call is intersected with the tenant's exact tool allowlist.
Optional tenant quotas reserve request and concurrency capacity atomically
before Scholar is contacted, then settle a durable lease when streaming ends.
Tenant administrators can inspect non-secret capability metadata and revoke a
capability immediately. Administration requests are database-rate-limited, and
Scholar calls use safe-method retries, bounded bodies, timeout classification,
and per-backend circuit isolation.

## Local development

Create an isolated environment and install the service:

```sh
python -m venv .venv
.venv/bin/pip install -e "services/proxy-hub/backend[dev]"
```

Run migrations and the API from `services/proxy-hub/backend`:

```sh
export PROXY_HUB_DATABASE_URL=postgresql+psycopg://proxy_hub:password@localhost:5432/proxy_hub
export PROXY_HUB_PUBLIC_ORIGIN=http://localhost:8080
export PROXY_HUB_OIDC_ISSUER_URL=https://identity.example.com
export PROXY_HUB_OIDC_CLIENT_ID=proxy-hub-local
export PROXY_HUB_OIDC_CLIENT_SECRET=replace-with-a-development-secret
export SCHOLAR_SERVICE_TOKEN=replace-with-a-development-service-token
export PROXY_HUB_BACKEND_PROBE_MAX_AGE_SECONDS=300
export PROXY_HUB_QUOTA_RESERVATION_TTL_SECONDS=600
export PROXY_HUB_ADMIN_RATE_LIMIT_REQUESTS=120
export PROXY_HUB_ADMIN_RATE_LIMIT_PERIOD_SECONDS=60
alembic upgrade head
uvicorn proxy_hub.app:app --reload
```

Registered Scholar backends reference service credentials as strict
`env:NAME` values, for example `env:SCHOLAR_SERVICE_TOKEN`.
Backend registration never stores or returns secret material. A platform
administrator must run a successful authenticated readiness probe before
activating a backend or an active tenant route; changes to the URL, corpus, or
credential reference invalidate the previous observation.
Quota enforcement remains disabled until a tenant quota policy explicitly
enables it. The reservation TTL is refreshed for active response streams.
Audit and usage endpoints require explicit timezone-aware `from` and `to`
parameters spanning no more than 31 days. Audit pages return only operational
identifiers, authorization decisions, backend/corpus selection, result class,
latency, response size, and quota delta. Usage pages aggregate gateway
requests, outcomes, latency, returned bytes, and current quota configuration
without reading request bodies or changing quota counters.

Production configuration fails closed unless the public origin uses HTTPS,
the browser session cookie uses the `__Host-` prefix, PostgreSQL is configured,
OIDC settings are secure, and the database is at the current Alembic head.
Run `proxy-hub-production-check` before rollout.

## Verification

```sh
ruff check .
ruff format --check .
mypy proxy_hub
pytest
```
