## ADDED Requirements

### Requirement: HTTP middleware stack compresses, scopes CORS, sets strict security headers, and rejects unbounded uploads

The application SHALL install `GZipMiddleware(minimum_size=1024)`. The credentialed CORS branch SHALL enumerate `allow_methods=["GET","POST","PATCH","DELETE","OPTIONS"]` and `allow_headers=["Authorization","Content-Type","X-Request-ID"]` (no wildcards) and SHALL set `expose_headers=["X-Request-ID","Retry-After"]`.

Every response SHALL carry:

- `Content-Security-Policy: default-src 'none'; frame-ancestors 'none'`
- `Referrer-Policy: no-referrer`
- `X-Content-Type-Options: nosniff`
- `Permissions-Policy: ()`

The `Server` and `X-Powered-By` response headers SHALL be stripped.

On the documentation routes (`/docs`, `/docs/oauth2-redirect`, `/redoc`, `/openapi.json`) AND only when `APP_ENABLE_DOCS=true`, a relaxed Content-Security-Policy MAY be applied to permit the CDN-hosted Swagger / ReDoc assets and inline scripts they require.

`ContentSizeLimitMiddleware` SHALL reject requests that declare `Transfer-Encoding: chunked` without a `Content-Length` header with `411 Length Required` and a Problem Details body.

#### Scenario: Large JSON response is compressed

- **GIVEN** a client sending `Accept-Encoding: gzip`
- **WHEN** an endpoint returns >1 KB JSON
- **THEN** the response header includes `Content-Encoding: gzip`

#### Scenario: Chunked upload with no Content-Length is rejected

- **WHEN** a client sends `POST /…` with `Transfer-Encoding: chunked` and no `Content-Length`
- **THEN** the response is `411 Length Required` with a Problem Details body

#### Scenario: X-Request-ID is JS-readable on credentialed responses

- **WHEN** a credentialed cross-origin request hits the API
- **THEN** the response carries `Access-Control-Expose-Headers: X-Request-ID, Retry-After`

#### Scenario: JSON endpoints carry the strict CSP

- **WHEN** any non-docs JSON endpoint returns a response
- **THEN** the response carries `Content-Security-Policy: default-src 'none'; frame-ancestors 'none'`
- **AND** `Referrer-Policy: no-referrer`
- **AND** `X-Content-Type-Options: nosniff`
- **AND** `Permissions-Policy: ()`
- **AND** does NOT carry `Server` or `X-Powered-By`

#### Scenario: Docs route gets the relaxed CSP

- **GIVEN** `APP_ENABLE_DOCS=true`
- **WHEN** `GET /docs` returns the Swagger UI
- **THEN** the response Content-Security-Policy allows scripts and styles from `https://cdn.jsdelivr.net`
- **AND** `frame-ancestors 'none'` is still set

#### Scenario: Docs route absent in production

- **GIVEN** `APP_ENABLE_DOCS=false`
- **WHEN** `GET /docs` is called
- **THEN** the response is 404
- **AND** every other response on the application carries the strict CSP

#### Scenario: Middleware-ordering regression is detected

- **GIVEN** the documented middleware order is security-headers (outermost) → CORS → rate-limit → request-context → content-size → gzip (innermost)
- **WHEN** a test inspects the installed middleware stack on `create_app()` and finds GZip wrapping the security-headers middleware (i.e. security headers absent from gzip-compressed responses), or finds `RequestContextMiddleware` outside `GZipMiddleware` (i.e. `X-Request-ID` missing on compressed responses)
- **THEN** the ordering test fails with a message naming both the offending and the expected order
- **AND** a compressed response on a representative JSON endpoint is verified to still carry the strict `Content-Security-Policy` and `X-Request-ID` headers

#### Scenario: Chunked upload with a Content-Length is allowed

- **WHEN** a client sends `POST /…` with both `Transfer-Encoding: chunked` AND a `Content-Length` header within the configured limit
- **THEN** the request is accepted (the 411 path triggers only when `Content-Length` is absent)
- **AND** the response is the normal endpoint response (not 411, not 413)

#### Scenario: Preflight for a disallowed header is rejected

- **WHEN** a client sends `OPTIONS /…` with `Access-Control-Request-Headers: X-Custom-Sniffing-Header`
- **THEN** the preflight response does not echo `X-Custom-Sniffing-Header` in `Access-Control-Allow-Headers`
- **AND** the subsequent cross-origin request carrying that header is blocked by the browser (the allow-list does not include it)
