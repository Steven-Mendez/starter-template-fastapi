## Why

Four middleware-layer defects compounding:

1. **No compression.** `GET /admin/users?limit=500` and `/admin/audit-events?limit=500` ship uncompressed JSON; large responses cost bytes and time.
2. **CORS `allow_methods=["*"]` and `allow_headers=["*"]` everywhere.** The credentialed branch should enumerate methods/headers; wildcards work but widen what cross-origin JS can probe. Also no `expose_headers=["X-Request-ID", "Retry-After"]`, so SPAs can't read those response headers from JS.
3. **`ContentSizeLimitMiddleware` only honours `Content-Length`.** Docstring admits "clients that omit Content-Length are not rejected." Any HTTP/1.1 client can send `Transfer-Encoding: chunked` with no `Content-Length` and stream gigabytes through.
4. **No baseline security headers.** Responses ship without `Content-Security-Policy`, `Referrer-Policy`, `X-Content-Type-Options`, or `Permissions-Policy`. The `Server` / `X-Powered-By` headers leak the stack identity.

## What Changes

- Add `GZipMiddleware(minimum_size=1024)` between `SecurityHeaders` and `RequestContext`.
- Replace CORS wildcards in the credentialed branch with explicit `allow_methods=["GET","POST","PATCH","DELETE","OPTIONS"]` and an explicit allow-list for headers (`Authorization`, `Content-Type`, `X-Request-ID`, `Idempotency-Key`).
- Add `expose_headers=["X-Request-ID", "Retry-After"]`.
- Set the following baseline response headers on every JSON endpoint:
  - `Content-Security-Policy: default-src 'none'; frame-ancestors 'none'` (strict; relaxed override below for docs).
  - `Referrer-Policy: no-referrer`.
  - `X-Content-Type-Options: nosniff`.
  - `Permissions-Policy: ()`.
- Apply a relaxed `Content-Security-Policy` ONLY on `/docs` and `/redoc` (when `APP_ENABLE_DOCS=true`) that allows the CDN-hosted Swagger / ReDoc assets and inline scripts they require.
- Strip `Server` and `X-Powered-By` response headers.
- In `ContentSizeLimitMiddleware`, also reject requests with `Transfer-Encoding: chunked` AND no `Content-Length` with `411 Length Required`. (Chosen over the stricter byte-counting alternative — see design.)

**Capabilities — Modified**: `project-layout`.

## Impact

- **Code**:
  - `src/app_platform/api/app_factory.py` — middleware registration order; CSP branching for docs.
  - `src/app_platform/api/middleware/content_size_limit.py` — chunked-no-length rejection.
- **Production**: smaller responses; tighter cross-origin surface; chunked DoS closed; strict CSP on JSON endpoints; stack identity not leaked.
