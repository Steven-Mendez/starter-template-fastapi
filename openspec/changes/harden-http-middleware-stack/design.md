## Context

Middleware tweaks that are individually trivial but collectively close several footguns. We bundle them because they all live in the same `app_factory.py` and are reviewable as one unit.

## Decisions

### GZip after SecurityHeaders, before RequestContext

Security headers (HSTS, X-Frame-Options, the new CSP) are set on the original response; GZip wraps. RequestContext stays innermost so the `X-Request-ID` header is emitted on compressed responses.

### Content-size: reject chunked-no-length (411), not byte-count streaming

**Chosen**: reject requests with `Transfer-Encoding: chunked` AND no `Content-Length` with `411 Length Required`. Simpler, well-supported by HTTP spec, no streaming machinery, no per-request bookkeeping.

**Rejected (alternative)**: wrap `request.receive` to count bytes; abort with 413 past `max_bytes`. More defensive against pathological clients that lie about `Content-Length` then keep streaming, but the implementation is fiddly inside Starlette's ASGI shape and adds per-byte overhead to legitimate uploads. We accept the residual risk; operators who want the stricter posture can add the byte-counter behind a feature flag in a follow-up.

### Concrete CORS lists, no wildcards

A maintenance burden when new headers land, but cheap. The initial `allow_headers` list is `["Authorization","Content-Type","X-Request-ID"]`.

### Baseline security headers (stricter alternative chosen)

The audit explicitly asked us to pick the stricter posture. We do:

| Header | Value | Rationale |
|---|---|---|
| `Content-Security-Policy` | `default-src 'none'; frame-ancestors 'none'` | JSON endpoints never need to load any resource. `frame-ancestors 'none'` prevents framing even by same-origin (X-Frame-Options is its predecessor; CSP is the modern source of truth). |
| `Referrer-Policy` | `no-referrer` | Strictest option; the API never benefits from sending a Referer header. |
| `X-Content-Type-Options` | `nosniff` | Disables MIME-sniffing on JSON responses. |
| `Permissions-Policy` | `()` | Empty policy = denies every browser feature (camera, microphone, geolocation, etc.). JSON responses never need any of them. |

We strip `Server` and `X-Powered-By` response headers — these only leak the stack identity without operational value. uvicorn's `--header` flag (or a middleware) removes them.

### Relaxed CSP for docs

`/docs` (Swagger UI) and `/redoc` need to load JS/CSS/font assets from a CDN (jsdelivr by default) and run inline scripts. The strict CSP above breaks both. We apply a per-route override:

```
Content-Security-Policy: default-src 'self';
  script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net;
  style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net;
  img-src 'self' data: https://fastapi.tiangolo.com;
  font-src 'self' https://cdn.jsdelivr.net;
  frame-ancestors 'none'
```

Applied only on `/docs`, `/docs/oauth2-redirect`, `/redoc`, and the `/openapi.json` endpoint — and only when `APP_ENABLE_DOCS=true`. In production (`APP_ENABLE_DOCS=false`) those routes are not mounted, and the strict CSP applies everywhere.

### Rationale summary

The Why field of the audit asked for the stricter posture as a forcing function: the API is JSON-only, so a deny-all CSP costs nothing on the API surface and only matters when serving HTML — which we explicitly carve out for `/docs` and `/redoc`. Stripping `Server`/`X-Powered-By` aligns with OWASP's "least information leakage" guidance.

## Non-goals

- **Not a WAF.** No request-body inspection, no signature-based attack detection, no rate-limiting beyond the existing per-route limiter; that surface remains the deployment ingress's job (CloudFront, ALB, Cloudflare, etc.).
- **Not byte-counted upload streaming.** The chunked-no-length rejection is the chosen defense; we explicitly punt on wrapping `request.receive` to count bytes mid-stream (see Decisions).
- **Not a TLS termination story.** HSTS and any TLS-redirect logic stay where they are (or remain the platform's responsibility); this change does not touch them.
- **Not OAuth/OIDC CORS for partner apps.** Cross-origin policy here serves the first-party SPA only; multi-tenant partner integrations are a separate design.
- **Not a docs-CSP minimization exercise.** The relaxed CSP for `/docs` permits jsdelivr-hosted assets and inline scripts as Swagger requires; tightening that further (self-hosting Swagger UI) is out of scope.

## Risks / Trade-offs

- **Risk**: GZip on small JSON adds CPU for no win. Mitigation: `minimum_size=1024`.
- **Risk**: a future feature returns HTML on a non-docs route; the strict CSP breaks it. Mitigation: that future change opts in to a route-specific CSP override the same way `/docs` does today; the test for that route catches the regression.

## Depends on

- None.

## Conflicts with

- `src/app_platform/api/app_factory.py` is shared with `add-error-reporting-seam`, `harden-rate-limiting`, `expose-domain-metrics`. Middleware registration order must be preserved — security headers SHOULD remain outermost, with rate-limit, request-context, content-size, and gzip in their documented order.
- `src/app_platform/api/middleware/content_size_limit.py` is owned by this change; no overlap.

## Migration

Single PR. Rollback: revert.
