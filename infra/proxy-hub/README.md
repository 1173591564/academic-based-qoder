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

Single-lab deployments configure the Scholar Streamable HTTP endpoint, corpus
version, and strict credential reference through the
`PROXY_HUB_SINGLE_LAB_*` variables. The Compose file passes these values to the
API and migrator containers so startup can bootstrap the route and keep its
readiness observation fresh. Inject the referenced secret, such as
`SCHOLAR_SERVICE_TOKEN`, through the deployment secret facility.

## Operations

Apply migrations as a one-shot operation before replacing API instances:

```sh
docker compose --env-file infra/proxy-hub/.env \
  -f infra/proxy-hub/compose.yml run --rm migrate
```

For production, run `proxy-hub-production-check` after the migration and before
traffic reaches a new API instance. Production startup repeats the migration
head check and fails closed when configuration or schema state is unsafe. See
`docs/proxy-hub-operations.md` for release, rollback, incident, and backup
procedures.

Back up the control plane with `pg_dump` and restore only into an empty, access-controlled control-plane PostgreSQL instance. Audit rows are append-only application records and must use retention and backup policies independent from operational logs.

Production deployments must terminate HTTPS at the same origin, set
`PROXY_HUB_ENVIRONMENT=production`, use a `__Host-` browser-session cookie,
inject the OIDC client secret through the deployment secret facility, keep
`/private/*` inaccessible from public ingress, and run migrations as a
separate release operation. The local Compose file is not a high-availability
production topology.

A non-loopback public HTTP origin is development-only and additionally requires
`PROXY_HUB_ALLOW_INSECURE_PUBLIC_HTTP=true`.

The public ingress accepts credential-validation CORS requests only from DSH
web clients served on HTTP loopback origins (`localhost`, `127.0.0.1`, or
`[::1]`). Other browser origins do not receive cross-origin access.

Scholar database credentials, corpus volumes, parsing jobs, and vector-index assets must not be added to this directory.
