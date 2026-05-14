## 1. Console adapter

- [x] 1.1a In `src/features/email/adapters/outbound/console/adapter.py` (currently the `_logger.info(... body=%s ...)` call at lines 47-53), replace the `body=%s` field with `body_len=%d body_sha256=%s` computed from `len(message.body)` and `hashlib.sha256(message.body.encode("utf-8")).hexdigest()`.
- [x] 1.1b In the same call, replace the `to=message.to` argument with `to=redact_email(message.to)`.
- [x] 1.2a Add `email_console_log_bodies: bool = False` to `EmailSettings` in `src/features/email/composition/settings.py` (env `APP_EMAIL_CONSOLE_LOG_BODIES`).
- [x] 1.2b In `ConsoleEmailAdapter.send`, emit the full-body log line only when `email_console_log_bodies` is `true` AND `APP_ENVIRONMENT=development`; otherwise emit only the `body_len`/`body_sha256` line.
- [x] 1.3 Add `APP_EMAIL_CONSOLE_LOG_BODIES=false` to `.env.example`.

## 2. Redaction primitives

- [x] 2.1 Add `redact_email(addr) -> str` to `app_platform/observability/redaction.py` (`f***@bar.com` form; preserve domain and first local char).
- [x] 2.2 Add the explicit constants in `redaction.py`:
  - `REDACT_STRICT_KEYS = frozenset({"password", "password_hash", "hash", "token", "access_token", "refresh_token", "authorization", "cookie", "set-cookie", "secret", "api_key", "phone"})`
  - `REDACT_EMAIL_KEYS = frozenset({"email", "to", "from", "recipient", "cc", "bcc"})`
  - `REDACT_HEADER_NAMES = frozenset({"authorization", "cookie", "set-cookie", "proxy-authorization", "x-api-key", "x-auth-token"})`

## 3. PII redaction processor and filter

- [x] 3.1 Implement `PiiRedactionProcessor` in `pii_filter.py` as a structlog processor (`(logger, method_name, event_dict) -> event_dict`).
- [x] 3.2 The processor walks `event_dict` keys (case-insensitive match):
  - keys in `REDACT_STRICT_KEYS` → value replaced with `"***REDACTED***"`.
  - keys in `REDACT_EMAIL_KEYS` → value passed through `redact_email(...)` (string values only).
- [x] 3.3 When the event contains a `headers`, `request.headers`, or `response.headers` mapping, apply `REDACT_HEADER_NAMES` (case-insensitive) and the strict/email rules to that nested mapping.
- [x] 3.4 Implement `PiiLogFilter(logging.Filter)` that applies the same redactions to `record.args` (when it's a mapping) and to any `extra=` keys promoted onto the record. Plain-string positional args are left alone (this filter does NOT scan values).
- [x] 3.5 Wire `PiiRedactionProcessor` into the structlog processor chain in `logging.py`. Mount `PiiLogFilter` on the root stdlib logger so uvicorn / third-party libs are covered.

## 4. Apply `redact_email` at call sites

- [x] 4.1a `src/features/email/adapters/outbound/smtp/adapter.py` — the success `event=email.smtp.sent` log (currently at line 87) must pass `to=redact_email(to)`.
- [x] 4.1b Same file, the error `event=email.smtp.failed` log (currently at line 79) must also pass `to=redact_email(to)`.
- [x] 4.2a `src/features/email/adapters/outbound/resend/adapter.py` — the success `event=email.resend.sent` log (currently at line 99) passes `to=redact_email(to)`.
- [x] 4.2b Same file, both `event=email.resend.failed` logs (currently at lines 90 and 107) must also pass `to=redact_email(to)`.
- [x] 4.3 In `src/features/outbox/application/use_cases/dispatch_pending.py`, when logging payloads on warn/error, route the payload dict through the structlog processor (which the chain already runs) — verify with a captured-log-record contract test that the rendered line contains no raw email or token.

## 5. uvicorn access log

- [x] 5.1 Disable uvicorn's `access` logger (or set its level above `INFO`) in `logging.py`.
- [x] 5.2 Add `AccessLogMiddleware` mounted **after** `RequestContextMiddleware` in `app_factory.py` that emits an INFO line with `method`, `path`, `status`, `duration_ms`, `request_id` (read from the contextvar).

## 6. Tests

- [x] 6.1 Unit: send a password-reset through the console adapter → captured log line contains `body_sha256=`, does NOT contain the raw URL/token.
- [x] 6.2 Unit: log call with `extra={"email": "foo@bar.com"}` → emitted line shows `email=f***@bar.com`.
- [x] 6.3 Unit: log call with `extra={"password": "hunter2"}` → emitted line shows `password=***REDACTED***`.
- [x] 6.4 Unit: log call with `extra={"headers": {"Authorization": "Bearer abc"}}` → header value redacted (case-insensitive match).
- [x] 6.5 Unit: each key in `REDACT_STRICT_KEYS` and `REDACT_EMAIL_KEYS` is exercised once (parametrized).
- [x] 6.6 Unit/e2e: access log line for `/me` contains a non-empty `request_id` matching the `X-Request-ID` response header.
- [x] 6.7 Regression: outbox-dispatch warn-path log capture contains no raw email or token.

## 7. Wrap-up

- [x] 7.1 Update `docs/observability.md` with the redaction contract, the explicit key set, and the env flags.
- [ ] 7.2 `make ci` green.
