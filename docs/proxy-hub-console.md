# Proxy Hub administration console

The console is a same-origin React application served under `/console/`. Existing OIDC authentication remains the administrator entry point. Research users receive Tokens and never use this interface.

## Navigation

The single-lab console has three routes:

| Route | Page | Purpose |
| --- | --- | --- |
| `/console/` | Token management | Create, search, rename, rotate, revoke, and delete Tokens |
| `/console/status` | Service status | View Scholar availability, Corpus version, last check, and run a probe |
| `/console/audit` | Audit log | View minimized Token request records |

Tenant, team, Membership, role, policy, quota, route, backend registry, Principal, enrolment, and usage pages are not part of the single-lab navigation.

## Token management

Creating a Token requires only a Token name. The server enforces normalized active-name uniqueness. A successful create or rotate response opens a one-time raw Token dialog with copy feedback. Closing an uncopied Token requires confirmation; after closing, the raw value cannot be retrieved.

Each row displays the Token name, display-safe Token prefix or suffix, status, creation time, and last-use time. Rename preserves the credential. Rotation invalidates the previous credential immediately. Revoke is reversible only by issuing a new Token. Delete revokes access, disables the managed identity records, and removes the Token from the active list while preserving audit data.

Create and rotate requests send an `Idempotency-Key`. Rename, rotate, revoke, and delete send the current ETag through `If-Match` when required. A stale ETag refreshes the list and reports a concurrency conflict rather than overwriting another administrator action.

## Service status

The page exposes only:

- available or unavailable;
- Corpus version;
- last checked time;
- probe action.

Scholar Backend URLs, deployment credentials, routes, and circuit details are not rendered. Development HTTP composition displays a plaintext transport warning.

## Audit log

Each row exposes:

- timestamp;
- Token name;
- MCP Tool;
- result;
- latency;
- Request ID.

Request parameters, research content, Token material, Principal IDs, tenant IDs, backend credentials, and raw MCP session identifiers are not available through the facade.

## Browser security

The frontend stores no OIDC access token, refresh token, Scholar Token, or Scholar Backend credential in local storage. Browser requests use the server-side session cookie, same-origin enforcement, CSRF cookie and header pair, and backend authorization. Hidden navigation is not an authorization control.

Lists and mutations provide loading, empty, error, unavailable, and denied states. Destructive actions require explicit confirmation, controls are keyboard accessible, and tables remain usable on narrow viewports.
