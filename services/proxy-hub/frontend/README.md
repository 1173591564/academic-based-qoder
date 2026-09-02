# Proxy Hub administration frontend

The frontend is a React and TypeScript administration SPA built with Vite and served from `/console/` on the same origin as the Hub API.

The current slice includes OIDC sign-in, control-plane overview, tenant listing and detail, platform-administrator tenant creation, and ETag-protected tenant status changes. Role capabilities returned by `/v1/admin/me` control presentation only; the backend remains authoritative.

The browser stores no identity-provider access or refresh token. Mutations use the server-side session cookie, same-origin checks, the CSRF cookie and header pair, and pessimistic response handling.

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
