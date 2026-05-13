## Why

Two concentrated pockets of avoidable typing debt (lands after `enable-strict-mypy` so these are actually flagged):

1. **`_principal_from_user(user: object)`** (`src/features/authentication/application/use_cases/auth/refresh_token.py:26-33`) — argument typed `object` solely to swallow 5 `attr-defined` ignores. The real type is the `UserPort.get_by_id` return contract.
2. **`class WorkerSettings: ...` empty** (`src/worker.py:128-135`) — declared empty then populated via `WorkerSettings.<attr> = ...` assignments, each silenced with `# type: ignore[attr-defined]`; the call site uses `settings_cls: Any` (`src/worker.py:141`). arq exposes a real shape we should declare.

Plus `dict[str, Any]` and `Sequence[Any]` proliferation in `src/features/outbox/composition/worker.py:46,65`, `src/features/outbox/composition/settings.py:44`, `src/features/background_jobs/composition/settings.py:27`. Most are legitimate (arq `ctx`); one is `Sequence[Any]` for `arq.cron.CronJob` which is a real type we can import.

## What Changes

- Define `UserSnapshot(Protocol)` in `src/features/users/application/dto.py` (or reuse the existing public DTO if its shape already matches) and use it for `_principal_from_user`.
- Type `WorkerSettings`: declare `functions: list[Function]`, `cron_jobs: list[CronJob]`, `redis_settings: RedisSettings`, `on_startup`, `on_shutdown`, `queue_name`.
- Replace `Sequence[Any]` with `Sequence[CronJob]` in `build_relay_cron_jobs(...)`.
- Drop unused `app: Any = None` parameters in composition settings.

**Capabilities — Modified**: `quality-automation`.

## Impact

- **Code**: `src/features/authentication/application/use_cases/auth/refresh_token.py`, `src/worker.py`, `src/features/outbox/composition/worker.py`, `src/features/outbox/composition/settings.py`, `src/features/background_jobs/composition/settings.py`, `src/features/users/application/dto.py` (new Protocol — or extension of an existing module).
- **`# type: ignore` removed**: at least 10.
- **Backwards compatibility**: none.
