## Why

Two tables grow forever:

1. **`refresh_tokens`** (`features/authentication/.../models.py:63-97`) is only soft-revoked. `LogoutUser` calls `revoke_refresh_token(record.id)`, never `DELETE`. Expired rows past `expires_at` stay forever too.
2. **`auth_internal_tokens`** (`models.py:128-158`) for password-reset and email-verify tokens — `used_at` is stamped, but nothing deletes the row.

After a few months of modest traffic both tables grow into the millions; indexes bloat; backups slow down.

## What Changes

- Add a `PurgeExpiredTokens` use case in `src/features/authentication/application/use_cases/maintenance/purge_expired_tokens.py` taking `retention_days: int`.
- Add repository methods `delete_expired_refresh_tokens(cutoff)` and `delete_expired_internal_tokens(cutoff)` that batch in 10k chunks.
- Register an arq cron job in `src/worker.py` that runs the use case every `APP_AUTH_TOKEN_PURGE_INTERVAL_MINUTES` (default 60).
- Add `APP_AUTH_TOKEN_RETENTION_DAYS` (default 7) and `APP_AUTH_TOKEN_PURGE_INTERVAL_MINUTES` (default 60) settings.

**Capabilities — Modified**: `authentication`.

## Impact

- **Code**:
  - `src/features/authentication/application/use_cases/maintenance/purge_expired_tokens.py` (new) — `PurgeExpiredTokens.execute(retention_days)`.
  - `src/features/authentication/application/ports/repository_port.py` — `delete_expired_refresh_tokens(cutoff)` and `delete_expired_internal_tokens(cutoff)` on the auth repo port.
  - `src/features/authentication/adapters/outbound/persistence/sqlmodel/repository.py` — SQL implementations with `LIMIT 10000` batches looping until empty.
  - `src/features/authentication/composition/settings.py` — `auth_token_retention_days: int = 7`, `auth_token_purge_interval_minutes: int = 60`.
  - `src/worker.py` — register an arq cron at the configured interval that wires the use case from the same composition root.
- **Tests**:
  - `src/features/authentication/tests/integration/` — seed 1000 expired refresh tokens + 500 expired internal tokens; run the use case; assert both tables have 0 rows past retention.
  - `src/features/authentication/tests/integration/` — assert unexpired and recently-revoked rows (within retention) are preserved.
- **Docs**:
  - `CLAUDE.md` env-var table — add `APP_AUTH_TOKEN_RETENTION_DAYS` and `APP_AUTH_TOKEN_PURGE_INTERVAL_MINUTES`.
  - `docs/operations.md` — note the new cron and how to disable it (set interval to 0 or undeploy the worker).
- **Production**: tables stay manageable; retention window aligns with the legal/compliance window for retaining session evidence after logout.
