## MODIFIED Requirements

### Requirement: Runtime dependencies are split into `core`, `api`, `worker`, and adapter extras

`pyproject.toml` `[project] dependencies` SHALL contain only the cross-cutting deps every layer needs (the **core** set). Role-specific deps SHALL live in `[project.optional-dependencies]`:

- `api` — `fastapi[standard]` and anything else only the API process needs.
- `worker` — `arq`, `redis`, and anything else only the background worker needs.
- `s3` — `boto3` for the S3 file-storage adapter.

There SHALL be no `resend` optional-dependency extra and no `httpx` runtime/test dependency declared for an email adapter: the Resend email adapter is removed and the only email adapter (`console`) has no third-party HTTP dependency. `python-multipart` SHALL appear in exactly one place (transitively via `fastapi[standard]` in the `api` extra), not as a direct dependency.

The S3 adapter's composition SHALL raise a clear startup error referencing the `s3` extra when `boto3` is missing.

#### Scenario: Default install lacks role-specific deps

- **GIVEN** a fresh `uv sync` with no extras
- **WHEN** the user inspects `uv pip list`
- **THEN** `fastapi`, `arq`, and `boto3` are all absent
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

#### Scenario: No resend extra is declared

- **GIVEN** the repository's `pyproject.toml`
- **WHEN** `[project.optional-dependencies]` is inspected
- **THEN** there is no `resend` key
- **AND** no `httpx` entry exists for an email adapter (neither in an extra nor in the `dev` dependency group)

#### Scenario: Missing s3 extra produces a clear startup error

- **GIVEN** `uv sync --extra api` (no `s3` extra) and `APP_STORAGE_BACKEND=s3` with `APP_STORAGE_ENABLED=true`
- **WHEN** the app starts
- **THEN** composition fails with an error message naming the `s3` extra
- **AND** the app does not silently start without a file-storage backend

### Requirement: docker-compose provides an SMTP catcher for dev

`docker-compose.yml` SHALL NOT ship a `mailpit` (or any other SMTP-catcher) service: no SMTP or Resend email backend exists, so a local SMTP sink would catch traffic the default `console` backend never sends. `.env.example` SHALL NOT include `APP_EMAIL_SMTP_*` keys, `APP_EMAIL_RESEND_*` keys, or a mailpit how-to comment block.

The `app` service SHALL declare `restart: unless-stopped` and a `healthcheck` hitting `/health/live`.

#### Scenario: No SMTP-catcher service is defined

- **GIVEN** the repository's `docker-compose.yml`
- **WHEN** `docker compose config --services` is listed
- **THEN** no `mailpit` service is present
- **AND** no remaining service declares a `depends_on` referencing `mailpit`

#### Scenario: App service marked unhealthy when /health/live fails

- **GIVEN** the `app` service is up but its `/health/live` endpoint returns a non-200 response (e.g. lifespan startup raised)
- **WHEN** the compose healthcheck retries past the configured `retries` budget
- **THEN** `docker compose ps` reports the `app` service as `unhealthy`
- **AND** the `restart: unless-stopped` policy attempts to restart it

#### Scenario: Default backend is unchanged

- **GIVEN** a developer runs `docker compose up` without overriding `APP_EMAIL_BACKEND`
- **WHEN** the API sends an email
- **THEN** the email is routed via the console backend (printed to stdout)
- **AND** no outbound SMTP or HTTP email-provider connection is attempted by any code path
