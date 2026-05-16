## MODIFIED Requirements

### Requirement: Documentation reflects the new layout

The system SHALL update `CLAUDE.md`, `README.md`, and any `docs/*.md` file that names internal modules to use post-refactor names (no `src.` prefix; `app_platform` rather than `platform` when referring to the project directory).

The documentation SHALL NOT instruct readers to recover the removed in-tree `_template` feature scaffold from git history, and SHALL NOT retain a `docs/feature-template.md` guide. Guidance for starting a new feature SHALL describe building the standard `domain/ application/ adapters/ composition/ tests/` layout from scratch following the documented hexagonal conventions, not copying or recovering a deleted scaffold. This restriction applies only to scaffold-recovery prose; unrelated uses of the words "template" and "scaffold" — the email `EmailTemplateRegistry` / `register_template` API and `docs/email.md`, and the file-storage feature's accurate "ships as scaffolding ready to be wired in" note (which describes the *feature being unwired by any consumer*, not the S3 *adapter* being incomplete) — are out of scope and SHALL remain.

The documentation SHALL NOT describe the `S3FileStorageAdapter` (`src/features/file_storage/adapters/outbound/s3/`) as a "stub", as raising `NotImplementedError`, or as a placeholder to be filled in for production. The S3 adapter is a real, runnable `boto3`-backed `FileStoragePort` implementation; any prose in `CLAUDE.md`, `README.md`, a `docs/*.md` file, or a feature `__init__.py` docstring that names the S3 adapter SHALL describe it as a real `boto3` adapter selectable via `APP_STORAGE_BACKEND=s3`. The accurate, code-true carve-out preserved by the previous paragraph is the *unwired-feature* "ships as scaffolding" note only; no "stub" / `NotImplementedError` characterisation of the adapter is blessed.

The `docs/api.md` API reference SHALL document only HTTP routes that exist in the inbound HTTP layer (`src/features/*/adapters/inbound/http/` and `src/app_platform/api/`). It SHALL NOT reference the fictional Kanban API (`/api/boards`, `/api/columns`, `/api/cards`) or any other endpoint, request/response schema, error code, header, or authentication mechanism that is not present in the source code.

#### Scenario: CLAUDE.md commands and module map use the new names

- **WHEN** a contributor reads `CLAUDE.md`
- **THEN** every code reference to an internal module (e.g. `src/platform/config/settings.py`, `src.main:app`, `python -m src.worker`) has been rewritten to use `src/app_platform/...`, `main:app`, and `python -m worker` respectively

#### Scenario: README and docs prose drop the `src.` prefix

- **WHEN** a contributor reads `README.md` or any file under `docs/`
- **THEN** no prose, command example, or import snippet uses `src.` as a Python import prefix; references to the source directory on disk (`src/`) remain unchanged

#### Scenario: Docs do not instruct recovering the removed scaffold

- **WHEN** a contributor reads `README.md`, `CLAUDE.md`, or any file under `docs/`
- **THEN** no prose, command example, or link instructs recovering the `_template` scaffold from git history (e.g. `git checkout <pre-removal-sha>^ -- src/features/_template`)
- **AND** no `docs/feature-template.md` file exists
- **AND** the "adding a new feature" guidance describes creating the `domain/ application/ adapters/ composition/ tests/` layout from scratch and wiring it through the authorization, email, and background-jobs registries with `require_authorization`-gated routes and no cross-feature imports
- **AND** the unrelated `EmailTemplateRegistry` / `register_template` references and the file-storage feature's "ships as scaffolding ready to be wired in" note are still present and unchanged

#### Scenario: API reference documents only routes that exist in code

- **WHEN** a contributor reads `docs/api.md`
- **THEN** the document contains no reference to `/api/boards`, `/api/columns`, `/api/cards`, or any Kanban board/column/card endpoint, schema, or error code
- **AND** the document contains no reference to an `X-API-Key` header or an `APP_WRITE_API_KEY` setting (no such authentication mechanism exists in the code)
- **AND** the document contains no `GET /health` route (only `GET /health/live` and `GET /health/ready` exist) and no `HealthRead` schema with `persistence.*`/`auth.*` fields
- **AND** every endpoint, request/response schema field, status code, response header, error `code`, and Problem-Type `type` URN documented is verifiable in `src/features/*/adapters/inbound/http/` or `src/app_platform/api/`
- **AND** the document states that the `email`, `background_jobs`, `file_storage`, and `outbox` features expose no inbound HTTP routes

#### Scenario: No documentation describes the real S3 adapter as a stub

- **WHEN** a contributor reads `README.md`, `CLAUDE.md`, any file under `docs/`, or the `src/features/file_storage/__init__.py` module docstring
- **THEN** no prose describes `S3FileStorageAdapter` (or "the S3 adapter") as a "stub", as raising `NotImplementedError`, or as a placeholder/scaffold to be implemented for production
- **AND** any prose that names the S3 file-storage adapter describes it as a real `boto3`-backed `FileStoragePort` implementation selectable via `APP_STORAGE_BACKEND=s3`
- **AND** the only S3/file-storage "scaffolding" wording that remains is the accurate statement that the `file_storage` *feature* ships unwired by any consumer (not a claim that the adapter itself is incomplete)

#### Scenario: README presents the AWS-first framing and a code-true feature inventory

- **WHEN** a contributor reads `README.md`
- **THEN** the introduction frames the project as an AWS-first FastAPI starter — local development needs no infrastructure beyond a Postgres container, production targets AWS, and the project ships one opinionated option rather than several half-built ones
- **AND** any AWS service named in the introduction (Cognito, SES, SQS, S3, RDS, ElastiCache) is presented as the project's production direction at a later roadmap step, not as an already-shipped adapter, endpoint, or configuration
- **AND** the Feature Inventory and Project Structure list all seven features present in the source tree — `authentication`, `users`, `authorization`, `email`, `background_jobs`, `file_storage`, and `outbox` — with no row or tree entry omitted
- **AND** no prose, table row, or tree entry references a removed adapter (`smtp`, `resend`, `arq`, `spicedb`/SpiceDB) or describes the S3 file-storage adapter as a "stub"
- **AND** the `file_storage` row describes a `local` adapter and a real `boto3`-backed `s3` adapter selectable via `APP_STORAGE_BACKEND=s3`
- **AND** the README contains no broken link to `openspec/changes/starter-template-foundation/` and no `src/cli/` command-reference section (the latter is owned by a later roadmap step)

#### Scenario: CLAUDE.md presents a code-true seven-feature inventory with no stale-adapter claims

- **WHEN** a contributor reads `CLAUDE.md`
- **THEN** the architecture overview prose states that **seven** features ship out of the box, consistent with the feature matrix in the same section and with the seven feature packages under `src/features/` (`authentication`, `users`, `authorization`, `email`, `background_jobs`, `file_storage`, `outbox`)
- **AND** the feature matrix contains a row for every one of those seven features, with no row omitted and no row referencing a removed adapter (`smtp`, `resend`, `arq`, `spicedb`/SpiceDB)
- **AND** the file-storage feature section describes the `s3` adapter as a real `boto3`-backed `FileStoragePort` implementation selectable via `APP_STORAGE_BACKEND=s3`, and no prose describes it as a "stub", as raising `NotImplementedError`, or as a placeholder
- **AND** the "adding a new feature" guidance describes creating the `domain/ application/ adapters/ composition/ tests/` layout from scratch, with no prose instructing recovery of a removed `_template` scaffold from git history
- **AND** the production checklist and key-env-vars prose match the per-feature `composition/settings.py` production validators (email refuses `console`, background_jobs refuses `in_process`, file-storage refuses `local` when `APP_STORAGE_ENABLED=true`, and outbox must be enabled in production)
- **AND** `CLAUDE.md` contains no `src/cli/` command-reference section (that is owned by a later roadmap step)
- **AND** the only `arq` references that remain state that `arq` was removed in ROADMAP ETAPA I step 5

#### Scenario: operations.md production narrative matches the live settings validators

- **WHEN** a contributor reads `docs/operations.md`
- **THEN** the Deployment Checklist contains no instruction to set `APP_WRITE_API_KEY` (or any other shared-key write-route setting), because no `composition/settings.py` projection or `src/app_platform/config/sub_settings.py` projection defines such a setting and write routes are authorized via `require_authorization`, not a shared API key
- **AND** the consolidated "the settings validator refuses to start when any of them are violated and `APP_ENVIRONMENT=production`" Environment Variable Reference lists only env vars that exist on a settings class, and every production-refusal it documents matches the four infrastructure `composition/settings.py:validate_production` validators (`email` refuses `console`, `background_jobs` refuses `in_process`, `file_storage` refuses `local` when `APP_STORAGE_ENABLED=true`, `outbox` must be enabled in production) and `AppSettings._validate_production_settings` (JWT secret/issuer/audience required, CORS no `*`, trusted hosts no wildcard, trusted proxies non-empty and never `0.0.0.0/0`, cookie secure and not `samesite=none`, docs disabled, RBAC enabled, return-internal-tokens false, Redis URL set)
- **AND** no surviving production-refusal statement or backend env-var row references a removed adapter (`smtp`, `resend`, `arq`, `spicedb`/SpiceDB) as a selectable backend, and the S3 file-storage adapter is described as the real `boto3`-backed production backend selectable via `APP_STORAGE_BACKEND=s3` (no "stub" / `NotImplementedError` / "placeholder" wording for the S3 adapter)
- **AND** the only `arq` references that remain state that `arq` was removed in ROADMAP ETAPA I step 5, and `docs/operations.md` contains no `src/cli/` command-reference catalogue (the incidental `python -m cli.create_super_admin` bootstrap-runbook mentions are operational prose, not a command catalogue, and remain unchanged)
- **AND** the destructive-migration `downgrade()` / `NotImplementedError` guard prose is unrelated to the S3 adapter and remains unchanged

#### Scenario: README.md and CLAUDE.md document the src/cli/ operational commands

- **WHEN** a contributor reads `README.md` and `CLAUDE.md` after ROADMAP ETAPA I step 12
- **THEN** `README.md` contains a CLI / operational-commands section (a dedicated subsection, not only the `make`-target table) that documents both `src/cli/` commands, and `CLAUDE.md` contains a corresponding `src/cli/` command group inside its `## Commands` block
- **AND** the documented invocation for the bootstrap-admin command is `PYTHONPATH=src uv run python -m cli.create_super_admin create-super-admin --email <email> --password-env <ENVVAR>` — the `create-super-admin` subcommand, a required `--email`, and `--password-env` (default `AUTH_BOOTSTRAP_PASSWORD`, naming the env var that holds the password so it stays out of shell history / process listings) — exactly matching the `argparse` definitions in `src/cli/create_super_admin.py`, with no invented flag or subcommand
- **AND** the bootstrap-admin documentation states it creates or promotes the first `system:main#admin`, is the on-demand alternative to the `APP_AUTH_SEED_ON_STARTUP` / `APP_AUTH_BOOTSTRAP_SUPER_ADMIN_EMAIL`/`APP_AUTH_BOOTSTRAP_PASSWORD` startup-bootstrap path (cross-referencing, not contradicting, the existing startup-bootstrap documentation), reads its configuration from `APP_*` environment variables via `AppSettings`, and that promoting an existing account requires `APP_AUTH_BOOTSTRAP_PROMOTE_EXISTING=true` plus the account's real password
- **AND** the documented invocation for the outbox-prune command is `make outbox-prune` (equivalently `PYTHONPATH=src uv run python -m cli.outbox_prune`), with no flags, matching `src/cli/outbox_prune.py` and the `Makefile` `outbox-prune` target
- **AND** the outbox-prune documentation states it is a one-shot prune of terminal (`delivered`/`failed`) outbox rows and stale dedup marks that runs the same `PruneOutbox` code path as the worker's prune cron, takes its retention/batch configuration from the `APP_OUTBOX_*` settings, and intentionally ignores `APP_OUTBOX_ENABLED`
- **AND** neither new section names a removed adapter (`_template`, `smtp`, `resend`, `arq`, `spicedb`/SpiceDB) nor describes the S3 file-storage adapter as a "stub", and no `src/cli/*.py` module, its docstring, the `Makefile`, any `docs/*.md` file, any other source file, any test, any migration, or any env var is changed by the edit (the docstring-vs-`Makefile` `PYTHONPATH=src` discrepancy is resolved in the docs by following the `Makefile` convention, not by editing code)
