## Context

Logs leak two distinct categories of data: PII (email addresses) and secrets (single-use tokens). The current code leaks both. Fix is a redaction filter on the logger plus targeted call-site sanitization at the places that produce the worst leaks (console email adapter — `printf` style body dump including the reset link).

## Decisions

- **Filter at the logger, not at every call site**: a single `logging.Filter` is the only way to catch incoming `extra` keys we haven't anticipated. Call-site redaction is for cases that pass *strings* (not structured fields).
- **Show `body_sha256`, not nothing**: operators need to correlate "the email I'm reading" with "the email the system tried to send" without reading the body itself. A SHA-256 of the rendered body is enough.
- **`redact_email(a***@example.com)`**: keeps domain (often useful for diagnostics) and first character (useful for "is this the right user?") but masks the local part.

## Risks / Trade-offs

- **Risk**: the filter over-redacts (matches a key called `token` that's a public idempotency token, not a secret). Mitigation: the filter is conservative; operators can extend the allow-list per-deployment if needed.
- **Trade-off**: filter runs on every log record (~1 µs). Trivial.

## Non-goals

- Regulatory-grade DLP. Redaction here is best-effort: a documented, closed key-name allowlist. It is not a substitute for a managed DLP pipeline, log-store-side scrubbing, or a GDPR audit.
- Value scanning / regex sweeps over message strings. Out of scope to keep the processor cheap and the rules legible; matching is by key name only.
- Schema enforcement on `extra=`. Loggers may pass arbitrary keys; the filter is the safety net, not a typed schema.
- Application-layer redaction of structured spans / metrics. Span attributes are governed by `improve-otel-instrumentation` (no raw email; use `user.email_hash`).
- Encrypting or sealing existing log archives. This change prevents new leaks; historical log retention/scrubbing is an operational concern.

## Migration

Single PR. Rollback safely if regressions appear — the filter can be removed without breaking anything.
