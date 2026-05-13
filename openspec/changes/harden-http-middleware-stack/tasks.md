## 1. GZip

- [ ] 1.1 In `app_factory.py`, add `app.add_middleware(GZipMiddleware, minimum_size=1024)`. Place it after security headers and before request context.

## 2. CORS hardening

- [ ] 2.1 In the credentialed CORS branch, replace `allow_methods=["*"]` with `["GET","POST","PATCH","DELETE","OPTIONS"]`.
- [ ] 2.2 Replace `allow_headers=["*"]` with `["Authorization","Content-Type","X-Request-ID"]`. (Idempotency-Key was previously planned but the corresponding seam change was cut; if reintroduced, append it here.)
- [ ] 2.3 Add `expose_headers=["X-Request-ID","Retry-After"]`.

## 3. Baseline security headers

- [ ] 3.1 Add (or extend) a security-headers middleware that sets, on every response:
  - `Content-Security-Policy: default-src 'none'; frame-ancestors 'none'`
  - `Referrer-Policy: no-referrer`
  - `X-Content-Type-Options: nosniff`
  - `Permissions-Policy: ()`
- [ ] 3.2 Strip `Server` and `X-Powered-By` response headers.
- [ ] 3.3 On `/docs`, `/docs/oauth2-redirect`, `/redoc`, `/openapi.json` (only when `APP_ENABLE_DOCS=true`), replace the strict CSP with the docs CSP defined in `design.md`.

## 4. Content-size hardening

- [ ] 4.1 In `ContentSizeLimitMiddleware.dispatch`, reject with `411 Length Required` (Problem Details body) when `Transfer-Encoding: chunked` is present and `Content-Length` is absent.

## 5. Tests

- [ ] 5.1 Hit a >1 KB JSON endpoint with `Accept-Encoding: gzip` → assert response is gzipped.
- [ ] 5.2 Preflight a non-allowed method (e.g. `OPTIONS … Access-Control-Request-Method: PUT`) → fail; allowed method → succeed.
- [ ] 5.3 Chunked POST with no Content-Length → 411.
- [ ] 5.4 Cross-origin response carries `Access-Control-Expose-Headers: X-Request-ID, Retry-After`.
- [ ] 5.5 JSON endpoint response carries the strict `Content-Security-Policy` and lacks `Server` / `X-Powered-By`.
- [ ] 5.6 `/docs` response carries the relaxed `Content-Security-Policy` allowing jsdelivr.
- [ ] 5.7 With `APP_ENABLE_DOCS=false`, `/docs` is not mounted and the strict CSP is the only one observed.

## 6. Wrap-up

- [ ] 6.1 `make ci` green.
