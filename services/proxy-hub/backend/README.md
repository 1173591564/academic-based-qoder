# Proxy Hub backend

The planned backend is a Python FastAPI service with three route groups:

- DSH session and MCP gateway routes;
- browser-session administration APIs;
- private health, metrics, and migration operations.

It is the only component allowed to read or mutate the Hub control-plane database, resolve secret references, evaluate authorization, route to Scholar, or append audit records.

Runtime code and dependencies will be added in the implementation phase.
