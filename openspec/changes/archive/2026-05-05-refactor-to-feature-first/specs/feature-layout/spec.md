## ADDED Requirements

### Requirement: Feature directory location

Every feature MUST live under `src/features/<feature-name>/` where `<feature-name>` is kebab-case (single word allowed). No production feature code MAY live outside `src/features/` except the `src/platform/` package.

#### Scenario: Adding a new feature
- **WHEN** a developer adds a new bounded context called `users`
- **THEN** all its code resides under `src/features/users/`
- **AND** no other directory in `src/` (apart from `src/platform/` and `src/main.py`) gains files belonging to it

### Requirement: Internal feature subdirectories

Every feature directory MUST contain at least the following subpackages: `domain/`, `application/`, `adapters/`, `composition/`. The `application/` subpackage MUST contain `ports/inbound/` and `ports/outbound/` subpackages. The `adapters/` subpackage MUST contain `inbound/` and `outbound/` subpackages.

#### Scenario: Kanban reference layout
- **WHEN** the Kanban feature is fully migrated
- **THEN** `src/features/kanban/` contains `domain/`, `application/{ports/inbound,ports/outbound,commands,queries,contracts,errors,use_cases}`, `adapters/{inbound/http,outbound/{persistence,query}}`, `composition/`

#### Scenario: Empty feature scaffold rejected
- **WHEN** a feature directory is missing one of `domain/`, `application/`, `adapters/`, `composition/`
- **THEN** the architecture conformance gate (`make lint-arch`) reports the missing structure or imports fail

### Requirement: Feature-private modules

Modules inside `src/features/<F>/` MUST NOT be imported by `src/features/<G>/` for any other feature `G`. Cross-feature communication, when needed, MUST go through ports defined inside the consuming feature.

#### Scenario: Cross-feature import detected
- **WHEN** `src/features/kanban/application/use_cases/...` imports from `src/features/users/...`
- **THEN** `make lint-arch` fails with a contract violation

### Requirement: Composition root per feature

Each feature MUST expose a single public registration function in `src/features/<F>/composition/wiring.py` that takes the FastAPI app and a platform container and registers all of the feature's routes and dependencies.

#### Scenario: Kanban registration
- **WHEN** `src/main.py` calls `register_kanban(app, platform)`
- **THEN** all Kanban HTTP routes are registered under `/api/...`
- **AND** all Kanban use case factories are wired against the platform's engine, clock, and id generator
