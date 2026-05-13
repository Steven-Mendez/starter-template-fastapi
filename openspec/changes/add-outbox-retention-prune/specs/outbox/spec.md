## ADDED Requirements

### Requirement: Outbox and dedup tables have a retention policy

A `PruneOutbox` use case SHALL delete:
- `outbox_messages` rows where `status='delivered' AND delivered_at < now() - APP_OUTBOX_RETENTION_DELIVERED_DAYS`.
- `outbox_messages` rows where `status='failed' AND failed_at < now() - APP_OUTBOX_RETENTION_FAILED_DAYS`.
- `processed_outbox_messages` rows where `processed_at < now() - 2 × APP_OUTBOX_RETRY_MAX_SECONDS`.

Deletions SHALL be batched in groups of at most `APP_OUTBOX_PRUNE_BATCH_SIZE` rows (default 1000) per transaction; the use case SHALL loop internally until the matching set is empty. The worker SHALL schedule `PruneOutbox.execute(...)` every 1 hour while `APP_OUTBOX_ENABLED=true`.

#### Scenario: Old delivered rows are removed; recent ones survive

- **GIVEN** 500 rows with `status='delivered'` and `delivered_at = now() - 30 days`
- **AND** 50 rows with `status='delivered'` and `delivered_at = now() - 1 day`
- **WHEN** the prune runs with `retention_delivered_days=7`
- **THEN** all 500 old rows are deleted
- **AND** all 50 recent rows remain

#### Scenario: Old failed rows obey their separate retention

- **GIVEN** 100 rows with `status='failed'` and `failed_at = now() - 40 days`
- **AND** 20 rows with `status='failed'` and `failed_at = now() - 25 days`
- **WHEN** the prune runs with `retention_failed_days=30`
- **THEN** the 100 rows older than 30 days are deleted
- **AND** the 20 rows newer than 30 days remain

#### Scenario: Dedup table is pruned at 2× retry window

- **GIVEN** `APP_OUTBOX_RETRY_MAX_SECONDS=900` (15 minutes)
- **AND** 200 `processed_outbox_messages` rows with `processed_at = now() - 1 hour`
- **AND** 50 `processed_outbox_messages` rows with `processed_at = now() - 5 minutes`
- **WHEN** the prune runs
- **THEN** the 200 rows older than 30 minutes are deleted
- **AND** the 50 recent rows remain

#### Scenario: Batch size bounds each transaction

- **GIVEN** `APP_OUTBOX_PRUNE_BATCH_SIZE=1000`
- **AND** 2500 `delivered` rows are eligible for deletion
- **WHEN** the prune runs
- **THEN** all 2500 rows are deleted across at least 3 internal transactions
- **AND** no single `DELETE` statement removes more than 1000 rows

#### Scenario: Mid-batch failure leaves remaining rows eligible for the next tick

- **GIVEN** 2500 `delivered` rows eligible for deletion and `prune_batch_size=1000`
- **AND** the second batch's transaction fails with a transient database error
- **WHEN** the prune runs
- **THEN** the first batch's 1000 rows have been deleted
- **AND** the remaining ~1500 rows still satisfy the eligibility predicate
- **AND** the next prune tick deletes them
- **AND** the relay's claim query for `pending` rows is unaffected (disjoint row set)

#### Scenario: Prune is opaque to non-pending rows' payloads

- **GIVEN** a `delivered` row whose `payload` contains arbitrary reserved keys (e.g. `__outbox_message_id`, `__trace`)
- **WHEN** the prune evaluates the row for deletion
- **THEN** the decision is based solely on `status` and `delivered_at`
- **AND** the payload is not read or modified

### Requirement: PruneOutbox is invocable as a one-shot CLI

`src/cli/outbox_prune.py` SHALL invoke the same `PruneOutbox` use case as the worker cron, using the same settings projection, and print a summary of rows deleted per table.

#### Scenario: Operator runs `make outbox-prune`

- **GIVEN** a configured environment with eligible rows in the database
- **WHEN** the operator runs `make outbox-prune`
- **THEN** the process exits with code 0
- **AND** stdout reports the number of rows deleted from each of `outbox_messages` (delivered), `outbox_messages` (failed), and `processed_outbox_messages`
