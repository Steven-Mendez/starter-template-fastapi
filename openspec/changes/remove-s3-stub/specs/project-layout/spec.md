## REMOVED Requirements

### Requirement: S3 adapter is configured for FastAPI concurrency

**Reason**: ROADMAP ETAPA I step 7 deletes `S3FileStorageAdapter` and its `boto3` dependency entirely. There is no boto3 client to size. A real, explicitly AWS-shaped `aws_s3` adapter (with its own concurrency configuration) is added at a later roadmap step; this concern is re-introduced by that change in AWS-adapter terms.

**Migration**: No action — the adapter and its dependency are removed; no deployment could have constructed this client without the (now-deleted) `s3` extra.

## MODIFIED Requirements

### Requirement: Documentation reflects the new layout

The system SHALL update `CLAUDE.md`, `README.md`, and any `docs/*.md` file that names internal modules to use post-refactor names (no `src.` prefix; `app_platform` rather than `platform` when referring to the project directory).

The documentation SHALL NOT instruct readers to recover the removed in-tree `_template` feature scaffold from git history, and SHALL NOT retain a `docs/feature-template.md` guide. Guidance for starting a new feature SHALL describe building the standard `domain/ application/ adapters/ composition/ tests/` layout from scratch following the documented hexagonal conventions, not copying or recovering a deleted scaffold. This restriction applies only to scaffold-recovery prose; unrelated uses of the words "template" and "scaffold" — the email `EmailTemplateRegistry` / `register_template` API and `docs/email.md` — are out of scope and SHALL remain. The documentation SHALL NOT describe the file-storage S3 adapter as a stub or as "scaffolding ready to be wired" (the S3 adapter is removed in ROADMAP ETAPA I step 7); file-storage documentation SHALL state that the `local` adapter is the only file-storage adapter and that production file storage arrives with the real AWS S3 adapter at a later roadmap step.

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
- **AND** the unrelated `EmailTemplateRegistry` / `register_template` references are still present and unchanged

#### Scenario: Docs do not describe the S3 adapter as a shipped stub

- **WHEN** a contributor reads `README.md`, `CLAUDE.md`, or any file under `docs/`
- **THEN** no prose describes a shipped S3 file-storage adapter, an S3 "stub", or an S3 adapter that "ships as scaffolding"
- **AND** the file-storage documentation states the `local` adapter is the only file-storage adapter and production file storage arrives with the real AWS S3 adapter at a later roadmap step
