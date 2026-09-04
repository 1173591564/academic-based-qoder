# Proxy Hub single-lab architecture

Proxy Hub is the security and routing boundary between DSH research clients and the Scholar Backend.

```text
Administrator browser --OIDC--> Proxy Hub console
                                  ├── Token management
                                  ├── Service status
                                  └── Audit log

DSH academic preset --Bearer Token--> /v1/me
                    --Bearer Token--> /v1/mcp/scholar
                                           │ deployment credential
                                           ▼
                                      Scholar Backend
                                      Corpus and 16 MCP Tools
```

The deployment owns one laboratory and one Corpus. Startup idempotently resolves the configured tenant, Scholar Backend, route, full Scholar tool policy, and administrator allowlist. Existing tenant, Principal, Membership, policy, quota, route, capability, and Access Key services remain internal compatibility mechanisms for one release.

## Token lifecycle

An administrator creates a Token by entering a Token name. Active names are unique after whitespace trimming, NFKC normalization, and case folding. The service creates a managed Principal and Membership, applies the fixed 16-tool policy, and issues a permanent Token with `expires_at = NULL`.

The raw Token is returned only by create and rotate operations. The database stores a cryptographic digest plus display-safe metadata. Rotation invalidates the previous Token immediately. Revoke disables access. Delete revokes the Token, disables the managed Principal and Membership, and retains audit history.

Legacy Access Keys keep their original expiry and quota behavior. New facade Tokens have no user quota but remain subject to global concurrency, request-size, timeout, safe-retry, and Scholar Backend circuit protections.

## DSH validation

DSH receives the Proxy Hub gateway URL from its deployment composition. The user enters only the Token. `GET /v1/me` uses `Authorization: Bearer <token>` and returns the Token name plus Scholar availability and Corpus version.

DSH persists `SCHOLAR_REMOTE_TOKEN` only after `/v1/me` succeeds with a nonempty `name`. Explicit `401` or `403` responses mean the credential is invalid. Network failures, timeouts, redirects, `5xx`, and malformed success responses are service failures and do not replace an existing Managed Credential.

The MCP client resolves the Managed Credential for every request. An explicit MCP `401` or `403` unsets the provider-managed value so onboarding can appear again. Other transport and Tool failures preserve it.

## Gateway behavior

Proxy Hub consumes the client Token, resolves the single-lab authorization records, verifies the requested MCP Tool, and selects the configured healthy Scholar Backend. It injects its own deployment credential upstream. The user Token is never forwarded.

MCP request and response bodies are relayed without model-visible rewriting. Research questions, request parameters, response bodies, raw Tokens, backend credentials, and raw MCP session identifiers are not persisted.

## Audit and retention

The administrator Audit log exposes only timestamp, Token name, MCP Tool, result, latency, and Request ID. Audit records are retained for 180 days and removed automatically. Revocation and deletion never erase unexpired audit records.

## Security

Production requires HTTPS or an encrypted private network. Public HTTP is development-only and requires explicit enablement in both Proxy Hub server configuration and DSH composition. HTTP exposes Tokens and research traffic in plaintext, so only revocable test Tokens may be used.

The console retains the existing OIDC browser session, CSRF, same-origin, role, and administrator allowlist controls. Research users do not log into the console.

## Public API

```text
GET    /v1/me
POST   /v1/mcp/scholar
GET    /v1/mcp/scholar
DELETE /v1/mcp/scholar

GET    /v1/admin/tokens
POST   /v1/admin/tokens
PATCH  /v1/admin/tokens/{token_id}
POST   /v1/admin/tokens/{token_id}/rotate
POST   /v1/admin/tokens/{token_id}/revoke
DELETE /v1/admin/tokens/{token_id}
GET    /v1/admin/service-status
POST   /v1/admin/service-status/probe
GET    /v1/admin/token-audit
```

Create operations require an `Idempotency-Key`. Mutations use ETags and `If-Match` where a current resource version is required. Only OIDC handshake routes redirect.
