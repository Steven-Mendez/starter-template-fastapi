## REMOVED Requirements

### Requirement: Things CRUD HTTP API
**Reason**: The `_template` feature ships the `things` resource as an executable scaffold for new projects, not as production functionality. Carrying it as a permanent live feature means it appears in the schema, the composition root, the authorization registry, and three Import Linter contracts forever. The scaffolding role is better served by docs and git history.
**Migration**: None. Clients calling `/things/*` will receive HTTP 404 after deploy. No production caller exists; the feature was documented as a copy-this-to-start-a-new-feature example. To use the scaffold for a new feature, copy it from git history (e.g., `git show <pre-removal-sha>:src/features/_template`) or from the `examples/kanban` branch.

The system SHALL no longer expose `POST/GET/PATCH/DELETE /things` or `POST /things/{id}/attachments`. The `things` table SHALL be dropped. The `thing` resource type SHALL no longer be registered with the authorization registry at startup. Any `relationships` rows with `resource_type='thing'` SHALL be deleted in the same migration that drops the table.

#### Scenario: Client calls a removed /things endpoint
- **WHEN** any HTTP client sends `GET /things`, `POST /things`, `GET /things/{id}`, `PATCH /things/{id}`, `DELETE /things/{id}`, or `POST /things/{id}/attachments` after deploy
- **THEN** the application returns HTTP 404 (route not mounted)
- **AND** no `_template` code path is reachable from the FastAPI router

#### Scenario: Database is migrated past the removal revision
- **WHEN** Alembic applies the drop-template-things revision on a deployed database
- **THEN** every row in `relationships` with `resource_type = 'thing'` is deleted
- **AND** the `things` table is dropped
- **AND** subsequent application boots succeed without registering a `thing` resource type or building a `_template` container

#### Scenario: Architecture contracts are checked
- **WHEN** `make lint-arch` runs after this change
- **THEN** no Import Linter contract references `src.features._template`
- **AND** all contracts pass (the email, background-jobs, and file-storage isolation contracts continue to forbid cross-feature imports for the remaining features)

#### Scenario: Operator looks for the scaffold
- **WHEN** a new operator follows the project docs to start a new feature
- **THEN** the docs point them at git history or the `examples/kanban` branch as the source of a worked CRUD example
- **AND** no `src/features/_template/` directory exists on `main`
