# Proxy Hub administration frontend

The frontend is a React and TypeScript administration SPA built with Vite and served from `/console/` on the same origin as the Hub API.

The console includes OIDC sign-in, overview, tenant detail, teams, memberships, role bindings, exact Scholar tool policy, quota policy, backend registry/readiness/credential rotation, explicit tenant routes, bounded audit, usage, and principal status administration.

Navigation and controls are derived from capabilities returned by `/v1/admin/me`, but the frontend is never the security boundary. Direct navigation and every API mutation remain subject to server-side role and tenant scope checks.

The browser stores no identity-provider access, refresh token, capability, or Scholar service credential in local storage. Mutations use the server-side session cookie, same-origin checks, the CSRF cookie and header pair, ETag/`If-Match` concurrency control, and `Idempotency-Key` for creation. Successful mutations display the returned server resource and refresh its ETag.

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
