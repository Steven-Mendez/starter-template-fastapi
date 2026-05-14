## 1. Use case

- [x] 1.1 Create `src/features/authentication/application/use_cases/maintenance/purge_expired_tokens.py`. Define `PurgeExpiredTokens.execute(retention_days: int) -> Result[PurgeReport, ApplicationError]` returning the deleted row counts per table.
- [x] 1.2 Add `delete_expired_refresh_tokens(cutoff: datetime) -> int` to the auth repo port. SQL: `DELETE FROM refresh_tokens WHERE id IN (SELECT id FROM refresh_tokens WHERE expires_at < :cutoff OR revoked_at < :cutoff LIMIT 10000)`; loop until the returned rowcount is 0.
- [x] 1.3 Add `delete_expired_internal_tokens(cutoff: datetime) -> int` to the auth repo port. SQL: `DELETE FROM auth_internal_tokens WHERE id IN (SELECT id FROM auth_internal_tokens WHERE used_at < :cutoff OR expires_at < :cutoff LIMIT 10000)`; loop until empty.

## 2. Settings

- [x] 2.1 Add `auth_token_retention_days: int = 7` to `AuthenticationSettings` (`src/features/authentication/composition/settings.py`); env var `APP_AUTH_TOKEN_RETENTION_DAYS`.
- [x] 2.2 Add `auth_token_purge_interval_minutes: int = 60` to the same settings; env var `APP_AUTH_TOKEN_PURGE_INTERVAL_MINUTES`.

## 3. Schedule

- [x] 3.1 In `src/worker.py`, register an arq cron at the configured interval that resolves `PurgeExpiredTokens` from the composition root and invokes `execute(retention_days=settings.authentication.auth_token_retention_days)`.

## 4. Tests

- [x] 4.1 Integration in `src/features/authentication/tests/integration/`: seed 1000 refresh-token rows with `expires_at = now() - 30 days`; run the use case with `retention_days=7`; assert all 1000 rows are gone.
- [x] 4.2 Integration: seed 500 internal-token rows with `used_at = now() - 30 days`; same outcome.
- [x] 4.3 Integration: seed rows within retention (e.g. `expires_at = now() - 1 day`); assert they are preserved after the purge.
- [x] 4.4 Integration: seed > 10000 expired rows; assert the use case deletes all of them (batched-loop coverage).

## 5. Docs

- [x] 5.1 Update `CLAUDE.md` "Key env vars (auth-related)" with `APP_AUTH_TOKEN_RETENTION_DAYS` and `APP_AUTH_TOKEN_PURGE_INTERVAL_MINUTES`.
- [x] 5.2 Update `docs/operations.md` describing the cron and the impact of disabling it.
- [ ] 5.3 `make ci` green.
