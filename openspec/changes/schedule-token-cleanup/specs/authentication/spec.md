## ADDED Requirements

### Requirement: Expired and revoked tokens are periodically purged

The authentication feature SHALL provide a `PurgeExpiredTokens` use case that deletes rows from `refresh_tokens` (where `expires_at` or `revoked_at` is older than the retention cutoff) and from `auth_internal_tokens` (where `used_at` or `expires_at` is older than the retention cutoff). The retention cutoff is `now() - APP_AUTH_TOKEN_RETENTION_DAYS` (default 7 days). The worker SHALL run the use case on a cron at the interval configured by `APP_AUTH_TOKEN_PURGE_INTERVAL_MINUTES` (default 60). Deletions MUST be batched (10000 rows per statement, looped until empty) to avoid long-running locks.

#### Scenario: Expired refresh-token rows are deleted

- **GIVEN** 100 refresh-token rows with `expires_at = now() - 30 days`
- **WHEN** `PurgeExpiredTokens.execute(retention_days=7)` runs
- **THEN** all 100 rows are deleted
- **AND** rows with `expires_at` within the last 7 days are preserved

#### Scenario: Expired internal-token rows are deleted

- **GIVEN** 500 internal-token rows with `used_at = now() - 30 days`
- **WHEN** `PurgeExpiredTokens.execute(retention_days=7)` runs
- **THEN** all 500 rows are deleted
- **AND** unused rows with `expires_at` in the future are preserved

#### Scenario: Large purges are batched

- **GIVEN** 30000 expired refresh-token rows
- **WHEN** the use case runs
- **THEN** all 30000 rows are deleted
- **AND** the implementation executed at least three batched `DELETE ... LIMIT 10000` statements

#### Scenario: Rows inside the retention window are preserved

- **GIVEN** a refresh-token row with `revoked_at = now() - 1 day` and `expires_at = now() + 7 days`
- **AND** an internal-token row with `used_at = now() - 1 day` and `expires_at = now() + 1 day`
- **WHEN** `PurgeExpiredTokens.execute(retention_days=7)` runs
- **THEN** both rows are still present
- **AND** the returned `PurgeReport` records zero deletions for each table
