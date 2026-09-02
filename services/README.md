# Deployable services

This repository is the backend workspace for the academic product. Service directories define deployable ownership; reusable Python code remains in `scholar/` and protocol adapters remain in `scholar_mcp/`.

- `scholar-backend/`: the existing single-corpus Scholar MCP data plane.
- `proxy-hub/`: the Phase Two authentication, policy, routing, quota, and audit control plane.

DeepSeek Harness is maintained in its own repository as the client/user-facing plane.
