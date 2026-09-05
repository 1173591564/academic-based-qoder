# Scholar infrastructure

`compose.yml` starts the current Scholar data-plane dependencies:

```sh
docker compose -f infra/scholar/compose.yml up -d
```

The Scholar v2 schema initializes PostgreSQL and pgvector. Relational,
embedding, graph, build, and serving-snapshot projections all live in this
single database; XML artifacts remain immutable files.

Production deployments must replace the local development credentials and must keep the backend administrative interface private.
