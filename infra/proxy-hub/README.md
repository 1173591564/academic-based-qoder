# Proxy Hub infrastructure

The local deployment starts an isolated PostgreSQL control database, a one-shot Alembic migrator, the FastAPI control-plane service, and an Nginx-served React console.

## Start locally

Register an OIDC client whose callback is `http://localhost:8080/auth/callback`, copy `.env.example` to `.env`, replace its placeholder values, then run:

```sh
docker compose --env-file infra/proxy-hub/.env \
  -f infra/proxy-hub/compose.yml up --build
```

Open `http://localhost:8080/console/`. The subject named by `PROXY_HUB_BOOTSTRAP_PLATFORM_ADMIN_SUBJECTS` receives the initial `platform_admin` role on its first successful OIDC callback.

The Nginx ingress exposes `/console/`, `/auth/*`, and `/v1/*`. Private health routes and PostgreSQL are available only on the Compose network.

Scholar backend registration stores only a strict environment reference such
as `env:SCHOLAR_SERVICE_TOKEN`. Inject the referenced value into the API
container, register the Scholar Streamable HTTP endpoint and corpus version,
run the authenticated probe, then activate the backend and tenant route.

## Operations

Apply migrations as a one-shot operation before replacing API instances:

```sh
docker compose --env-file infra/proxy-hub/.env \
  -f infra/proxy-hub/compose.yml run --rm migrate
```

Back up the control plane with `pg_dump` and restore only into an empty, access-controlled control-plane PostgreSQL instance. Audit rows are append-only application records and must use retention and backup policies independent from operational logs.

Production deployments must terminate HTTPS at the same origin, set `PROXY_HUB_ENVIRONMENT=production`, inject the OIDC client secret through the deployment secret facility, keep `/private/*` inaccessible from public ingress, and run migrations as a separate release operation. The local Compose file is not a high-availability production topology.

Scholar database credentials, corpus volumes, parsing jobs, and vector-index assets must not be added to this directory.
