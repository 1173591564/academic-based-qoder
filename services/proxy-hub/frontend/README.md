# Proxy Hub administration frontend

The planned frontend is a React/TypeScript administration SPA built with Vite and served from the same HTTPS origin as the Hub API.

It manages tenants, teams, principals, role bindings, tool policy, quotas, Scholar backend routes, health, and audit views through `/v1/admin/`. It does not make authorization decisions, store provider tokens, call Scholar directly, or provide the DSH research interface.

Runtime code and dependencies will be added in the implementation phase.
