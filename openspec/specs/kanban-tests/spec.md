# kanban-tests Specification

## Purpose
TBD - created by archiving change testing-suite-foundation. Update Purpose after archive.
## Requirements
### Requirement: In-memory fakes for every Kanban outbound port

`src/features/kanban/tests/fakes/` MUST provide an in-memory implementation for every Kanban outbound port: `InMemoryKanbanRepository` (covers command and lookup ports), `InMemoryUnitOfWork` (implements `UnitOfWorkPort`), `InMemoryQueryRepository` (implements `KanbanQueryRepositoryPort`), `FixedClock` (`ClockPort`), `SequentialIdGenerator` (`IdGeneratorPort`), plus a `RecordingUoW` decorator for asserting commit/rollback calls and a `FakeAppContainer` that wires them together for HTTP overrides.

#### Scenario: Fakes satisfy port contracts
- **WHEN** the fakes are used as the SUT in the contract test suites
- **THEN** every contract scenario passes

### Requirement: Domain unit tests

`src/features/kanban/tests/unit/domain/` MUST contain tests covering: `Board.add_column`, `Board.delete_column`, `Board.move_card` (intra-column, inter-column, invalid target), `Board.find_column_containing_card`, `Board.get_card`, `Column.insert_card`, `Column.move_card_within`, `Column.extract_card`, `Card.apply_patch` (each field, including `clear_due_at`), `CardPriority` ordering, and `ValidCardMoveSpecification.is_satisfied_by` for every branch.

#### Scenario: Move card to invalid target
- **WHEN** `Board.move_card` is called with a target column that does not exist
- **THEN** the result is `Err(KanbanError.INVALID_CARD_MOVE)`

#### Scenario: Apply patch with no changes is rejected at use case
- **WHEN** the domain `Card.apply_patch` receives all `None` arguments
- **THEN** the card is unchanged

### Requirement: Use case unit tests

For every Kanban use case under `src/features/kanban/application/use_cases/`, a corresponding test module under `src/features/kanban/tests/unit/application/` MUST exist and cover: the happy path, every error branch (missing aggregate, invalid input, empty patch), and the transactional contract (`commit()` is called exactly once on success; `rollback()` is called when an exception escapes the use case body, verified via `RecordingUoW`).

#### Scenario: CreateBoard happy path
- **WHEN** `CreateBoardUseCase.execute(CreateBoardCommand(title="Roadmap"))` runs against the fakes
- **THEN** the result is `Ok(AppBoardSummary(...))`
- **AND** the `RecordingUoW` reports exactly one `commit()` call

#### Scenario: PatchCard with no changes
- **WHEN** `PatchCardUseCase.execute` is called with a command whose `has_changes()` returns False
- **THEN** the result is `Err(ApplicationError.PATCH_NO_CHANGES)`
- **AND** the `RecordingUoW` reports zero commits

#### Scenario: Domain error mapped to application error
- **WHEN** a domain method returns `Err(KanbanError.CARD_NOT_FOUND)`
- **THEN** the use case converts it to `Err(ApplicationError.CARD_NOT_FOUND)` via `from_domain_error`

#### Scenario: Unhandled exception triggers rollback
- **WHEN** an outbound port raises during `execute`
- **THEN** the `RecordingUoW` reports zero commits and one rollback (or context-manager exit triggers it)

### Requirement: Reusable port contract suites

`src/features/kanban/tests/contracts/` MUST expose parameterized suites: `kanban_repository_contract`, `query_repository_contract`, `unit_of_work_contract`. Each suite MUST be runnable against any implementation by passing a SUT factory fixture. Both the in-memory fake (in `unit/`) and the SQLModel implementation (in `integration/persistence/`) MUST consume the same suite.

#### Scenario: Same suite, two implementations
- **WHEN** the test runner executes the kanban repository contract
- **THEN** the same set of contract test functions runs once against `InMemoryKanbanRepository` and once against `SessionSQLModelKanbanRepository`

### Requirement: Persistence integration tests

`src/features/kanban/tests/integration/persistence/` MUST start a Postgres testcontainer (session-scoped), apply the existing Alembic migrations, and run the contract suites plus tests for the concurrency constraints introduced by migration `20260427_0002_persistence_concurrency_constraints`.

#### Scenario: Concurrency constraint enforced
- **WHEN** two concurrent updates target the same Kanban aggregate version
- **THEN** the second update is rejected per the constraint added in revision `20260427_0002`

### Requirement: HTTP adapter tests via dependency overrides

`src/features/kanban/tests/e2e/` MUST build a real `app = create_app(test_settings)` and override `get_app_container` with a `FakeAppContainer`. Tests MUST cover: each Kanban operation's success path, validation errors (HTTP 422), missing aggregates (HTTP 404), domain conflicts (HTTP 409), missing API key on writes (HTTP 401), and the Problem+JSON shape (RFC 9457: `type`, `title`, `status`, `detail`, `instance`, plus the `code` and `request_id` extensions used by this template). At least one happy-path e2e test per resource MUST run with the testcontainer Postgres engine attached (no fakes) to verify the wired-up flow.

#### Scenario: Problem+JSON shape on 404
- **WHEN** a `GET /api/boards/{id}` request hits an unknown id
- **THEN** the response status is 404
- **AND** the response media type is `application/problem+json`
- **AND** the body contains `type`, `title`, `status`, `instance`, `code = "board_not_found"`, and a `request_id` matching the `X-Request-ID` header

#### Scenario: Write rejected without API key
- **WHEN** `APP_WRITE_API_KEY` is set in `test_settings` and a `POST /api/boards` request omits `X-API-Key`
- **THEN** the response status is 401
