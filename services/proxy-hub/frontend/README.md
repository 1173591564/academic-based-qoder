# Proxy Hub administration frontend

The frontend is a React and TypeScript administration SPA built with Vite and served from `/console/` on the same origin as the Hub API.

The console includes OIDC sign-in and three administrator pages:

- Token management: create, copy once, rename, rotate, revoke, delete, and search Tokens;
- Service status: Scholar availability, Corpus version, last check, and an explicit probe;
- Audit log: timestamp, Token name, MCP Tool, result, latency, and Request ID.

Tenant, membership, policy, quota, route, backend credential, and Principal administration remain backend compatibility APIs and are not exposed in the single-lab console. The frontend is never the security boundary; every API mutation remains subject to the administrator role or allowlist.

The browser stores no identity-provider access token, refresh token, raw Scholar Token, or Scholar Backend credential in local storage. Mutations use the server-side session cookie, same-origin checks, the CSRF cookie and header pair, ETag/`If-Match` concurrency control, and `Idempotency-Key`. A raw Token is rendered only from a create or rotate response, with copy feedback and a close confirmation when it has not been copied.

## Development

```sh
npm install
npm run dev
```

The Vite development server proxies `/auth/*` and `/v1/*` to `http://127.0.0.1:8000`.

## Verification

```sh
npm test
npm run typecheck
npm run build
npm audit --audit-level=high
```
