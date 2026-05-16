## MODIFIED Requirements

### Requirement: Runtime dependencies are split into `core`, `api`, `worker`, and adapter extras

`pyproject.toml` `[project] dependencies` SHALL contain only the cross-cutting deps every layer needs (the **core** set). Role-specific deps SHALL live in `[project.optional-dependencies]`:

- `api` — `fastapi[standard]` and anything else only the API process needs.
- `worker` — `redis` (used by the auth distributed rate limiter and the principal cache) and anything else the Redis-using roles need. The `worker` extra SHALL NOT declare `arq`: the `arq` adapter and worker runtime are removed (ROADMAP ETAPA I step 5); the production job runtime (AWS SQS + a Lambda worker) is added at a later roadmap step.
- `s3` — `boto3` for the S3 file-storage adapter.

There SHALL be no `resend` optional-dependency extra and no `httpx` runtime/test dependency declared for an email adapter: the Resend email adapter is removed and the only email adapter (`console`) has no third-party HTTP dependency. There SHALL be no `arq` entry in any optional-dependency extra or in the `dev` dependency group. `python-multipart` SHALL appear in exactly one place (transitively via `fastapi[standard]` in the `api` extra), not as a direct dependency.

The S3 adapter's composition SHALL raise a clear startup error referencing the `s3` extra when `boto3` is missing.

#### Scenario: Default install lacks role-specific deps

- **GIVEN** a fresh `uv sync` with no extras
- **WHEN** the user inspects `uv pip list`
- **THEN** `fastapi`, `boto3`, and `arq` are all absent
- **AND** `uv.lock` resolves successfully (the core set installs cleanly)

#### Scenario: API role install brings only the API deps

- **GIVEN** `uv sync --extra api`
- **WHEN** the user inspects the resolved install
- **THEN** `fastapi[standard]` and (transitively) `python-multipart` are present
- **AND** `arq` is absent

#### Scenario: Worker role install brings redis but no arq

- **GIVEN** `uv sync --extra worker`
- **WHEN** the user inspects the resolved install
- **THEN** `redis` is present (the auth rate limiter and principal cache use it)
- **AND** `arq` is absent (the worker runtime arrives at a later roadmap step)
- **AND** `fastapi[standard]` is absent

#### Scenario: No resend extra is declared

- **GIVEN** the repository's `pyproject.toml`
- **WHEN** `[project.optional-dependencies]` is inspected
- **THEN** there is no `resend` key
- **AND** no `httpx` entry exists for an email adapter (neither in an extra nor in the `dev` dependency group)

#### Scenario: No arq dependency is declared anywhere

- **GIVEN** the repository's `pyproject.toml`
- **WHEN** every `[project.optional-dependencies]` extra and the `dev` dependency group are inspected
- **THEN** no entry declares `arq`
- **AND** `uv.lock` contains no `arq` package after `uv lock` is regenerated

#### Scenario: Missing s3 extra produces a clear startup error

- **GIVEN** `uv sync --extra api` (no `s3` extra) and `APP_STORAGE_BACKEND=s3` with `APP_STORAGE_ENABLED=true`
- **WHEN** the app starts
- **THEN** composition fails with an error message naming the `s3` extra
- **AND** the app does not silently start without a file-storage backend

### Requirement: Strategic `Any`/`object` hotspots are typed

The `_principal_from_user` helper in `src/features/authentication/application/use_cases/auth/refresh_token.py` SHALL accept a `UserSnapshot` Protocol parameter (not `object`). The cron-descriptor builders SHALL return a typed `Sequence` of a runtime-agnostic descriptor (not `Sequence[Any]`) and SHALL reference no `arq` type: the `arq` `WorkerSettings` class and `Sequence[CronJob]` annotations are removed with the `arq` adapter and worker runtime (ROADMAP ETAPA I step 5); the production job runtime (AWS SQS + a Lambda worker) re-specifies its own typed runtime surface at a later roadmap step.

#### Scenario: No silenced attribute-error ignores remain in `refresh_token.py`

- **GIVEN** the codebase after this change lands
- **WHEN** `rg "type: ignore\[attr-defined\]" src/features/authentication/application/use_cases/auth/refresh_token.py` runs
- **THEN** there are zero matches

#### Scenario: Cron descriptor sequences are typed

- **GIVEN** `src/features/outbox/composition/worker.py` and `src/features/authentication/composition/worker.py`
- **WHEN** mypy checks the files under strict mode
- **THEN** the cron-descriptor builder return annotations are a concrete `Sequence[<CronDescriptor>]` (not `Sequence[Any]`) and reference no `arq` type
- **AND** no `# type: ignore` is needed at any call site

#### Scenario: Passing a non-conforming object to `_principal_from_user` fails type-check

- **GIVEN** a hypothetical caller that passes an object lacking `authz_version` to `_principal_from_user`
- **WHEN** mypy checks the caller under strict mode
- **THEN** mypy reports a structural-protocol violation against `UserSnapshot`
- **AND** the failure surfaces at the call site, not inside `_principal_from_user` (so no new `# type: ignore` is needed there)
