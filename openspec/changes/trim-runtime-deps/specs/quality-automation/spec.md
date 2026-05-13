## ADDED Requirements

### Requirement: Runtime dependencies are split into `core`, `api`, `worker`, and adapter extras

`pyproject.toml` `[project] dependencies` SHALL contain only the cross-cutting deps every layer needs (the **core** set). Role-specific deps SHALL live in `[project.optional-dependencies]`:

- `api` — `fastapi[standard]` and anything else only the API process needs.
- `worker` — `arq`, `redis`, and anything else only the background worker needs.
- `resend` — `httpx` for the Resend email adapter.
- `s3` — `boto3` for the S3 file-storage adapter.

`python-multipart` SHALL appear in exactly one place (transitively via `fastapi[standard]` in the `api` extra), not as a direct dependency.

The Resend adapter's composition SHALL raise a clear startup error referencing the `resend` extra when `httpx` is missing. The S3 adapter SHALL do the same for `boto3` and the `s3` extra.

#### Scenario: Default install lacks role-specific deps

- **GIVEN** a fresh `uv sync` with no extras
- **WHEN** the user inspects `uv pip list`
- **THEN** `httpx`, `fastapi`, `arq`, and `boto3` are all absent
- **AND** `uv.lock` resolves successfully (the core set installs cleanly)

#### Scenario: API role install brings only the API deps

- **GIVEN** `uv sync --extra api`
- **WHEN** the user inspects the resolved install
- **THEN** `fastapi[standard]` and (transitively) `python-multipart` are present
- **AND** `arq` and `redis` are absent

#### Scenario: Worker role install brings only the worker deps

- **GIVEN** `uv sync --extra worker`
- **WHEN** the user inspects the resolved install
- **THEN** `arq` and `redis` are present
- **AND** `fastapi[standard]` is absent

#### Scenario: Resend extra brings httpx

- **GIVEN** `uv sync --extra api --extra resend`
- **WHEN** the API process starts with `APP_EMAIL_BACKEND=resend`
- **THEN** `httpx` is in the resolved install
- **AND** the Resend adapter composes successfully

#### Scenario: Missing extra produces a clear startup error

- **GIVEN** `uv sync --extra api` (no `resend` extra) and `APP_EMAIL_BACKEND=resend`
- **WHEN** the app starts
- **THEN** composition fails with an error message naming the `resend` extra (e.g. `"install with: uv sync --extra resend"`)
- **AND** the app does not silently start without an email transport
