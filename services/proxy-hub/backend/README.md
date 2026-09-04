# Proxy Hub backend

The backend is a Python FastAPI control-plane service. The current route groups are:

- OIDC login and callback routes under `/auth/`;
- DSH enrolment exchange and holder revocation under `/v1/session`;
- authenticated Scholar Streamable HTTP MCP under `/v1/mcp/scholar`;
- Token validation under `/v1/me`;
- single-lab Token, Service status, and Audit log APIs under `/v1/admin/`;
- browser-session administration APIs under `/v1/admin/`;
- private liveness and readiness routes under `/private/health/`.

It is the only component allowed to mutate the Hub control-plane database, evaluate authorization, or append audit records. It resolves deployment-owned Scholar credentials only while forwarding an MCP request; raw Tokens, Scholar credentials, MCP session identifiers, and research arguments are not persisted in control-plane records.

Startup idempotently resolves the configured single-lab tenant, Scholar Backend route, full Scholar tool policy, and administrator allowlist. The Token facade reuses the internal Principal, Membership, Access Key, policy, route, and audit services while hiding those resources from the console. Legacy Access Keys retain their configured expiry and quota behavior.

New facade Tokens use `expires_at = NULL`, grant all 16 Scholar MCP Tools, and remain active until rotation or revoke. Token names are unique among active Tokens after trim, NFKC normalization, and case folding. Deletion revokes the Token, disables its managed Principal and Membership, and preserves audit records.

Administration requests are database-rate-limited. Scholar calls retain global concurrency, bounded request and response bodies, timeout classification, safe-method retries, and per-backend circuit isolation.

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
export PROXY_HUB_SINGLE_LAB_TENANT_SLUG=scholar-lab
export PROXY_HUB_SINGLE_LAB_TENANT_NAME="Scholar Lab"
export PROXY_HUB_SINGLE_LAB_BACKEND_NAME="Scholar Backend"
export PROXY_HUB_SINGLE_LAB_BACKEND_URL=https://scholar.example/mcp
export PROXY_HUB_SINGLE_LAB_CORPUS_VERSION=corpus-v1
export PROXY_HUB_SINGLE_LAB_BACKEND_CREDENTIAL_REF=env:SCHOLAR_SERVICE_TOKEN
export PROXY_HUB_AUDIT_RETENTION_DAYS=180
alembic upgrade head
uvicorn proxy_hub.app:app --reload
```

Registered Scholar backends reference service credentials as strict
`env:NAME` values, for example `env:SCHOLAR_SERVICE_TOKEN`.
Backend registration never stores or returns secret material. A platform
administrator must run a successful authenticated readiness probe before
activating a backend or an active tenant route; changes to the URL, corpus, or
credential reference invalidate the previous observation.
`GET /v1/me` distinguishes invalid credentials from an unavailable Scholar Backend and returns the Token name plus Scholar availability and Corpus version. The simplified audit facade returns only Token name, MCP Tool, timestamp, result, latency, and Request ID. Audit request parameters and bodies are not stored, and startup removes audit records older than 180 days.

Legacy quota enforcement remains disabled until a tenant quota policy explicitly enables it. The reservation TTL is refreshed for active response streams.

Production configuration fails closed unless the public origin uses HTTPS,
the browser session cookie uses the `__Host-` prefix, PostgreSQL is configured,
OIDC settings are secure, and the database is at the current Alembic head.
Run `proxy-hub-production-check` before rollout.

Public HTTP is development-only and requires both the deployment environment and the DSH composition to opt in explicitly. Use only revocable test Tokens over HTTP.

## Verification

```sh
ruff check .
ruff format --check .
mypy proxy_hub
pytest
```
