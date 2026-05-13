## ADDED Requirements

### Requirement: Strategic `Any`/`object` hotspots are typed

The `_principal_from_user` helper in `src/features/authentication/application/use_cases/auth/refresh_token.py` SHALL accept a `UserSnapshot` Protocol parameter (not `object`). The arq `WorkerSettings` class in `src/worker.py` SHALL declare typed class attributes for every field it actually uses (`functions`, `cron_jobs`, `redis_settings`, `on_startup`, `on_shutdown`, `queue_name`). The cron-job builders SHALL return `Sequence[CronJob]`, not `Sequence[Any]`.

#### Scenario: No silenced attribute-error ignores remain in `refresh_token.py`

- **GIVEN** the codebase after this change lands
- **WHEN** `rg "type: ignore\[attr-defined\]" src/features/authentication/application/use_cases/auth/refresh_token.py` runs
- **THEN** there are zero matches

#### Scenario: WorkerSettings exposes typed attributes

- **GIVEN** the codebase after this change lands
- **WHEN** a contributor introspects `WorkerSettings` via `inspect.get_annotations(WorkerSettings)`
- **THEN** the returned dict contains entries for `functions`, `cron_jobs`, `redis_settings`, `on_startup`, `on_shutdown`, `queue_name`
- **AND** the call site `arq.run_worker(WorkerSettings)` no longer needs an `Any` cast

#### Scenario: CronJob sequences are typed

- **GIVEN** `src/features/outbox/composition/worker.py:build_relay_cron_jobs`
- **WHEN** mypy checks the file under strict mode
- **THEN** the return annotation is `Sequence[CronJob]` (not `Sequence[Any]`)
- **AND** no `# type: ignore` is needed at any call site

#### Scenario: Passing a non-conforming object to `_principal_from_user` fails type-check

- **GIVEN** a hypothetical caller that passes an object lacking `authz_version` to `_principal_from_user`
- **WHEN** mypy checks the caller under strict mode
- **THEN** mypy reports a structural-protocol violation against `UserSnapshot`
- **AND** the failure surfaces at the call site, not inside `_principal_from_user` (so no new `# type: ignore` is needed there)
