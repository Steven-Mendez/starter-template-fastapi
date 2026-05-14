## 1. UserSnapshot Protocol

- [x] 1.1 Declare `UserSnapshot(Protocol)` in `src/features/users/application/dto.py` (or reuse the existing public DTO if its shape already matches `UserPort.get_by_id`'s return).
- [x] 1.2 In `src/features/authentication/application/use_cases/auth/refresh_token.py`, replace `def _principal_from_user(user: object) -> Principal:` with `def _principal_from_user(user: UserSnapshot) -> Principal:`.
- [x] 1.3 Remove the 5 `# type: ignore[attr-defined]` lines in that function.

## 2. Typed WorkerSettings

- [x] 2.1 In `src/worker.py`, declare class attributes on `WorkerSettings` with their real arq types: `functions: list[Function]`, `cron_jobs: list[CronJob]`, `redis_settings: RedisSettings`, `on_startup`, `on_shutdown`, `queue_name`.
- [x] 2.2 Drop the `Any` cast at the `arq.run_worker(WorkerSettings)` call site.
- [x] 2.3 Drop `attr-defined` `# type: ignore` lines that were silencing the empty-class accesses.

## 3. CronJob typing

- [x] 3.1 In `src/features/outbox/composition/worker.py`, replace `Sequence[Any]` with `Sequence[CronJob]` on `build_relay_cron_jobs(...)`.
- [x] 3.2 In `src/features/outbox/composition/settings.py` and `src/features/background_jobs/composition/settings.py`, drop unused `app: Any = None` parameters.

## 4. Verify

- [x] 4.1 `make typecheck` clean (under the strict gate from `enable-strict-mypy`).
- [x] 4.2 `rg "type: ignore\[attr-defined\]" src/features/authentication/application/use_cases/auth/refresh_token.py` returns zero matches.
- [x] 4.3 `make ci` green.
