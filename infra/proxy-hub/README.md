# Proxy Hub infrastructure

Proxy Hub deployment assets will live here once the interfaces in `docs/proxy-hub.md` and `docs/proxy-hub-console.md` are implemented.

The target deployment provides:

- one HTTPS origin for `/console/`, `/v1/session`, `/v1/mcp/`, and `/v1/admin/`;
- a control-plane PostgreSQL database isolated from Scholar databases;
- deployment secret-manager integration for identity-provider and Scholar credentials;
- private health, metrics, migration, backup, and restore access;
- independently configurable retention for audit and operational data.

Scholar database credentials, corpus volumes, parsing jobs, and vector-index assets must not be added to this directory.
