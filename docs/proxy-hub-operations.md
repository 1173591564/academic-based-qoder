# Proxy Hub operations

## Release gate

Run releases against a dedicated PostgreSQL control database. The API refuses
to start in production when configuration is insecure or the database is not
at every Alembic head.

Required production settings include:

- `PROXY_HUB_ENVIRONMENT=production`;
- an HTTPS `PROXY_HUB_PUBLIC_ORIGIN`;
- a `PROXY_HUB_COOKIE_NAME` beginning with `__Host-`;
- a complete HTTPS OIDC configuration with a non-placeholder client secret;
- PostgreSQL rather than SQLite;
- `PROXY_HUB_AUDIT_FAILURE_POLICY=fail_closed`.

Before replacing API instances:

```sh
pg_dump --format=custom --file=proxy-hub-before-release.dump "$PROXY_HUB_DATABASE_URL"
alembic upgrade head
proxy-hub-production-check
```

The preflight prints no credentials. It validates configuration, database
connectivity, and the exact migration head.

## Rollout and rollback

Apply migrations as a separate release operation, then roll API instances and
the console. Keep private health endpoints off the public ingress.

For an application rollback, deploy the previous application image first.
Additive columns and tables remain compatible with the preceding Proxy Hub
release. Only downgrade the database after restoring or verifying a backup:

```sh
alembic downgrade 2b734c8dd831
```

The downgrade removes administration rate counters and the capability version
column. Never downgrade while newer API instances are still serving traffic.

## Runtime controls

Administration requests use a PostgreSQL-backed fixed window keyed by the
opaque browser-session digest. Rejections return `429`, `Retry-After`, and
`RateLimit-*` headers and create a minimized audit event.

Scholar gateway requests use bounded connect/request timeouts. Only MCP `GET`
requests are retried; `POST` and `DELETE` are sent once so retries cannot
duplicate tool mutations, quota reservations, or audit events. Repeated
transport, redirect, authentication, or `5xx` failures open an isolated
per-backend circuit. Open circuits return `503` with `Retry-After`.

Request and response bodies are bounded. The client capability is consumed by
Proxy Hub and is never forwarded; Scholar receives only the independently
resolved service credential.

Audit writes share the protected transaction with control-plane mutations and
authorization decisions. An audit write or commit failure rolls back the
operation or terminates the gateway request; events are never silently
dropped.

## Capability and access incidents

For a leaked DSH capability, revoke it from the tenant capability registry.
The holder can also call `DELETE /v1/session` with the capability itself.
Revocation is immediate for later MCP requests and removes stored MCP session
affinity.

Disabling a principal, tenant, membership, or team also makes existing
capabilities fail closed on their next authentication. Rotate a Scholar
credential reference through the backend administration API, probe readiness,
and only then reactivate routing.

## Backup and monitoring

Back up the control database with encrypted `pg_dump` artifacts and test
restores into an empty access-controlled PostgreSQL instance. Give append-only
audit records a retention policy independent from application logs.

Alert on:

- public `5xx`, `backend_timeout`, and `backend_unavailable` rates;
- repeated circuit-open and Scholar readiness failures;
- administration and tenant quota `429` rates;
- migration-head or private readiness failures;
- control-database saturation and backup failures.

Use bounded audit and usage APIs for incident review. They intentionally omit
request bodies, research content, raw capabilities, session digests, argument
digests, and credentials.
