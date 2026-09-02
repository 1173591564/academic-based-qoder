# Scholar infrastructure

`compose.yml` starts the current Scholar data-plane dependencies:

```sh
docker compose -f infra/scholar/compose.yml up -d
```

`init.sql` initializes PostgreSQL and pgvector. The existing Neo4j service is retained for compatibility with current local workflows while the tracked skill and command assets are migrated to the in-memory graph implementation.

Production deployments must replace the local development credentials and must keep the backend administrative interface private.
