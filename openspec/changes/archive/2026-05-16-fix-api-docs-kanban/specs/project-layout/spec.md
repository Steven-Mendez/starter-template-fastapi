## MODIFIED Requirements

### Requirement: Documentation reflects the new layout

The system SHALL update `CLAUDE.md`, `README.md`, and any `docs/*.md` file that names internal modules to use post-refactor names (no `src.` prefix; `app_platform` rather than `platform` when referring to the project directory).

The documentation SHALL NOT instruct readers to recover the removed in-tree `_template` feature scaffold from git history, and SHALL NOT retain a `docs/feature-template.md` guide. Guidance for starting a new feature SHALL describe building the standard `domain/ application/ adapters/ composition/ tests/` layout from scratch following the documented hexagonal conventions, not copying or recovering a deleted scaffold. This restriction applies only to scaffold-recovery prose; unrelated uses of the words "template" and "scaffold" — the email `EmailTemplateRegistry` / `register_template` API and `docs/email.md`, and the file-storage S3 "ships as scaffolding" stub note — are out of scope and SHALL remain.

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
- **AND** the unrelated `EmailTemplateRegistry` / `register_template` references and the file-storage S3 "ships as scaffolding" note are still present and unchanged

#### Scenario: API reference documents only routes that exist in code

- **WHEN** a contributor reads `docs/api.md`
- **THEN** the document contains no reference to `/api/boards`, `/api/columns`, `/api/cards`, or any Kanban board/column/card endpoint, schema, or error code
- **AND** the document contains no reference to an `X-API-Key` header or an `APP_WRITE_API_KEY` setting (no such authentication mechanism exists in the code)
- **AND** the document contains no `GET /health` route (only `GET /health/live` and `GET /health/ready` exist) and no `HealthRead` schema with `persistence.*`/`auth.*` fields
- **AND** every endpoint, request/response schema field, status code, response header, error `code`, and Problem-Type `type` URN documented is verifiable in `src/features/*/adapters/inbound/http/` or `src/app_platform/api/`
- **AND** the document states that the `email`, `background_jobs`, `file_storage`, and `outbox` features expose no inbound HTTP routes
