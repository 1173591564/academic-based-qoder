# Deployable services

This repository is the backend workspace for the academic product. Service directories define deployable ownership; reusable Python code remains in `scholar/` and protocol adapters remain in `scholar_mcp/`.

- `scholar-backend/`: the existing single-corpus Scholar MCP data plane.
- `proxy-hub/backend/`: the Phase Two authentication, policy, routing, quota, audit, and administration API.
- `proxy-hub/frontend/`: the operator-facing web administration console.

DeepSeek Harness is maintained in its own repository as the client/user-facing plane.
