## Why

Three log-hygiene defects:

1. **Console email adapter logs the full body at INFO** — `features/email/adapters/outbound/console/adapter.py:47-53` writes `to=%s … body=%s`. The body for password-reset includes the raw single-use token. Anyone with log read access can complete a reset they did not request, even in staging.
2. **PII (email) in multiple INFO log lines** — SMTP/Resend adapters (`smtp/adapter.py:87`, `resend/adapter.py:99-107`) and the outbox dispatch path log `to=...` from `SEND_EMAIL_JOB` payloads on warn/error. Turns the log store into a PII system under GDPR/HIPAA scrutiny.
3. **uvicorn access log lines miss `request_id`** — `RequestContextMiddleware` sets `x-request-id` on responses but uvicorn's `%(message)s` access record runs outside that middleware's context, so structured access lines emit `request_id=null` for every line.

## What Changes

- Redact reset/verify tokens in the console adapter: log `body_len=N` and `body_sha256=…` instead of the body. Gate full-body logging behind `APP_ENVIRONMENT=development` AND a new `APP_EMAIL_CONSOLE_LOG_BODIES=false` flag.
- Add a `redact_email(addr)` helper (`a***@example.com`) and apply it at every adapter that currently logs the raw `to` field.
- Add `PiiRedactionProcessor`, a **structlog processor** (not value scanning) that walks each event dict and redacts by **key-name allowlist**. The redacted key set is fixed and explicit:
  - **Strict redaction (`***REDACTED***`)**: `password`, `password_hash`, `hash`, `token`, `access_token`, `refresh_token`, `authorization`, `cookie`, `set-cookie`, `secret`, `api_key`, `phone`.
  - **Email masking (`redact_email`)**: `email`, `to`, `from`, `recipient`, `cc`, `bcc`.
  - **Header deny-list (same treatment as above)**: when an event contains a `headers` mapping (or `request.headers` / `response.headers`), the processor SHALL apply the same allowlist to its keys case-insensitively. Header names always redacted: `authorization`, `cookie`, `set-cookie`, `proxy-authorization`, `x-api-key`, `x-auth-token`.
  - Matching is **case-insensitive** on the exact key name. Value scanning / regex over message strings is explicitly NOT in scope.
- Install the processor in the structlog processor chain in `app_platform/observability/logging.py` and as a `logging.Filter` mounted on the root stdlib logger so plain-stdlib log calls (uvicorn, third-party libs) are also covered.
- Route uvicorn access logs through Starlette middleware that emits the line *after* `RequestContextMiddleware` has set the contextvar.

**Capabilities — Modified**: `project-layout`.

## Impact

- **Code**:
  - `src/app_platform/observability/logging.py` (structlog chain wiring; install stdlib filter).
  - `src/app_platform/observability/redaction.py` (new) — `redact_email(addr) -> str`, the redacted-key constants.
  - `src/app_platform/observability/pii_filter.py` (new) — `PiiRedactionProcessor` (structlog) + `PiiLogFilter` (stdlib).
  - `src/app_platform/api/middleware/access_log.py` (new) — `AccessLogMiddleware`.
  - `src/app_platform/api/app_factory.py` — mount `AccessLogMiddleware` after `RequestContextMiddleware`.
  - `src/features/email/adapters/outbound/console/adapter.py` — body redaction, `redact_email(to)`.
  - `src/features/email/adapters/outbound/smtp/adapter.py:87` — `redact_email(to)`.
  - `src/features/email/adapters/outbound/resend/adapter.py:99-107` — `redact_email(to)`.
  - `src/features/email/composition/settings.py` — `email_console_log_bodies: bool = False`.
  - `src/features/outbox/application/use_cases/dispatch_pending.py` — payload logging uses redacted view; verify with test.
- **Tests**: `src/app_platform/tests/unit/observability/test_pii_filter.py`, plus regression tests under each email adapter.
- **Docs**: `docs/observability.md` (redaction contract, env flags, explicit redacted-key list).
- **Env**: `.env.example` adds `APP_EMAIL_CONSOLE_LOG_BODIES=false`.
- **Production**: log lines no longer carry tokens or raw emails by default; a regression test catches re-introductions.

## Depends on

- None hard. Pairs with `add-gdpr-erasure-and-export` (shared PII inventory) and `propagate-trace-context-through-jobs` / `fix-outbox-dispatch-idempotency` (both also touch `dispatch_pending.py`).

## Conflicts with

- `fix-outbox-dispatch-idempotency`, `propagate-trace-context-through-jobs`, `improve-otel-instrumentation` — all touch `dispatch_pending.py`. Coordinate landing order.
- `clean-architecture-seams` — touches `features/email/composition/jobs.py` and the email adapter call surface; ensure the new `redact_email` call site lands in the relocated handler.
- `add-gdpr-erasure-and-export` — overlapping PII inventory; align the key list.
