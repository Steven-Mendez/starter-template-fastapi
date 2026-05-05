# architecture-docs Specification

## Purpose
TBD - created by archiving change feature-template-and-docs. Update Purpose after archive.
## Requirements
### Requirement: hex-design-guide reflects feature-first layout

`hex-design-guide.md` MUST describe the feature-first layout (`src/platform/` + `src/features/<F>/...`) and MUST NOT reference the legacy `src/{api,application,domain,infrastructure}` directories except in a clearly labeled "Migration from layer-first" section.

#### Scenario: Guide aligned with code
- **WHEN** a reader follows the guide
- **THEN** every example path resolves to an existing module in the repository

### Requirement: hex-design-guide documents inbound port convention

`hex-design-guide.md` MUST contain a section that defines the convention "one inbound `Protocol` per use case, named `<UseCase>UseCasePort`, located in `src/features/<F>/application/ports/inbound/<verb>_<noun>.py`" and MUST explain why HTTP adapters depend on the Protocol rather than the concrete class.

#### Scenario: Inbound convention explained
- **WHEN** a developer searches the guide for "inbound"
- **THEN** the convention is documented with a Kanban code reference

### Requirement: hex-design-guide documents conformance contracts

`hex-design-guide.md` MUST list every import-linter contract enforced by the repository, with a one-sentence rationale per contract and a link to the failing-case example.

#### Scenario: Contracts visible in docs
- **WHEN** a contract violation occurs in CI
- **THEN** the developer can find the violated contract in the guide and read its rationale

### Requirement: Root README reflects feature-first layout

The root `README.md` MUST contain accurate "Quick start", "Project layout", "Add a new feature", "Conformance", and "OpenSpec" sections matching the actual filesystem after the `refactor-to-feature-first` and `testing-suite-foundation` changes are archived. The "Quick start" MUST mention `fastapi dev` (not raw `uvicorn`) and MUST mention `make test` and `make ci`.

#### Scenario: Quick start works as written
- **WHEN** a fresh user runs the commands listed under "Quick start" in order
- **THEN** the API serves on port 8000 and `/health` returns `200 OK`

### Requirement: README links to template

The root `README.md` MUST contain a section "Add a new feature" that links to `src/features/_template/README.md` and gives the one-line summary "copy `_template/`, follow its README, register in `src/main.py`".

#### Scenario: Discoverability
- **WHEN** a new contributor reads the root README
- **THEN** they find the link to the template README within the first two screens of content

### Requirement: Migration note for old clones

The root `README.md` MUST contain a short "Migration from layer-first" subsection summarizing the path renames so users who cloned the previous version of the template can update their fork.

#### Scenario: Migration note present
- **WHEN** an old-clone user reads the README
- **THEN** they find a list mapping `src/api/...` → `src/features/<F>/adapters/inbound/http/...`, `src/application/...` → `src/features/<F>/application/...`, `src/domain/...` → `src/features/<F>/domain/...`, `src/infrastructure/...` → `src/features/<F>/adapters/outbound/...` plus `src/platform/...`
