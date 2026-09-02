# Proxy Hub backend

The backend is a Python FastAPI control-plane service. The current route groups are:

- OIDC login and callback routes under `/auth/`;
- browser-session administration APIs under `/v1/admin/`;
- private liveness and readiness routes under `/private/health/`.

It is the only component allowed to read or mutate the Hub control-plane database, evaluate authorization, or append audit records. Scholar credential resolution and routing are not part of this foundation slice.

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
alembic upgrade head
uvicorn proxy_hub.app:app --reload
```

Production configuration fails closed unless the public origin uses HTTPS, PostgreSQL is configured, and all OIDC settings are present.

## Verification

```sh
ruff check .
ruff format --check .
mypy proxy_hub
pytest
```
