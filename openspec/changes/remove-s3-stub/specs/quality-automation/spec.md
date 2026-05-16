## MODIFIED Requirements

### Requirement: Runtime dependencies are split into `core`, `api`, `worker`, and adapter extras

`pyproject.toml` `[project] dependencies` SHALL contain only the cross-cutting deps every layer needs (the **core** set). Role-specific deps SHALL live in `[project.optional-dependencies]`:

- `api` — `fastapi[standard]` and anything else only the API process needs.
- `worker` — `redis` (used by the auth distributed rate limiter and the principal cache) and anything else the Redis-using roles need. The `worker` extra SHALL NOT declare `arq`: the `arq` adapter and worker runtime are removed (ROADMAP ETAPA I step 5); the production job runtime (AWS SQS + a Lambda worker) is added at a later roadmap step.

There SHALL be no `s3` optional-dependency extra and no `boto3`, `botocore`, or `moto` dependency declared for a file-storage adapter (neither in an extra nor in the `dev` dependency group): the S3 file-storage adapter is removed in ROADMAP ETAPA I step 7 and the only file-storage adapter (`local`) has no third-party dependency. The real, explicitly AWS-shaped file-storage adapter (`aws_s3`) and its dependency are added at a later roadmap step. There SHALL be no `resend` optional-dependency extra and no `httpx` runtime/test dependency declared for an email adapter: the Resend email adapter is removed and the only email adapter (`console`) has no third-party HTTP dependency. There SHALL be no `arq` entry in any optional-dependency extra or in the `dev` dependency group. `python-multipart` SHALL appear in exactly one place (transitively via `fastapi[standard]` in the `api` extra), not as a direct dependency.

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

#### Scenario: No s3 extra or boto3 dependency is declared

- **GIVEN** the repository's `pyproject.toml`
- **WHEN** `[project.optional-dependencies]` and the `dev` dependency group are inspected
- **THEN** there is no `s3` key
- **AND** no entry declares `boto3`, `botocore`, `boto3-stubs`, or `moto`
- **AND** `uv.lock` contains no `boto3`/`botocore`/`moto` package after `uv lock` is regenerated

### Requirement: Integration markers reflect real-backend usage

A test marked `integration` SHALL exercise the real backend (real Postgres / real Redis via testcontainers). Tests that use in-memory stubs (`fakeredis`, etc.) MUST be marked `unit` instead.

#### Scenario: fakeredis-backed test is not labeled integration

- **GIVEN** `src/features/background_jobs/tests/integration/test_arq_round_trip.py` (which uses `fakeredis`)
- **WHEN** the test marker is inspected after this change lands
- **THEN** it is marked `unit`, not `integration` (and the file moves under a `tests/unit/` path if marker convention requires)
- **AND** a sibling `test_arq_redis_round_trip.py` exists with the `integration` marker against real Redis via `testcontainers`

#### Scenario: No moto-backed test is labeled integration

- **GIVEN** the repository test suite after ROADMAP ETAPA I step 7
- **WHEN** every `integration`-marked test is inspected
- **THEN** none exercises an S3/`moto` backend (the S3 adapter and `moto` dependency are removed)
