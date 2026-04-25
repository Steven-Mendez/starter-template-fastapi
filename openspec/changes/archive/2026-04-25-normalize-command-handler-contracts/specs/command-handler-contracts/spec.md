# Spec: Normalize Command Handler Contracts and Result Types

**Capability**: command-handler-contracts
**Change**: normalize-command-handler-contracts

---

## ADDED Requirements

### Requirement: NCH-01 — `handle_create_board` returns `AppResult` like all other command handlers

**Priority**: Medium

`KanbanCommandInputPort.handle_create_board` MUST return `AppResult[AppBoardSummary, ApplicationError]` so the command input port has a uniform contract surface and consistent error handling semantics.

**Acceptance Criteria**:
1. `KanbanCommandInputPort.handle_create_board` return type is `AppResult[AppBoardSummary, ApplicationError]`.
2. All command methods in `KanbanCommandInputPort` return `AppResult[..., ApplicationError]`.
3. `KanbanCommandHandlers.handle_create_board` returns `AppOk(AppBoardSummary(...))` on success.
4. If board creation fails, `KanbanCommandHandlers.handle_create_board` returns `AppErr(ApplicationError)` instead of raising domain-level flow exceptions.

#### Scenario: Handler returns `AppOk` for successful board creation

- Given: `KanbanCommandHandlers` configured with working repository, `IdGenerator`, and `Clock`
- When: `handle_create_board(CreateBoardCommand(title="Test"))` is called
- Then: the method returns `AppOk`
- And: `AppOk.value` is an `AppBoardSummary` containing the generated board ID and timestamp

#### Scenario: Port consumers handle create board with standard `AppResult` matching

- Given: code that pattern-matches command handler results via `case AppOk(value)` and `case AppErr(err)`
- When: it calls `handle_create_board`
- Then: no special-case direct return handling is required

### Requirement: NCH-02 — `POST /boards` router handles `AppResult` via match statement

**Priority**: Medium

The `create_board` endpoint in `src/api/routers/boards.py` MUST pattern-match on `AppResult` from `handle_create_board`, aligning with the existing write-endpoint error mapping pattern.

**Acceptance Criteria**:
1. The endpoint uses `match commands.handle_create_board(...)`.
2. The `AppOk` branch returns `to_board_summary_response(value)`.
3. The `AppErr` branch delegates to `raise_http_from_application_error(err)`.
4. Successful `POST /boards` requests still return HTTP 201 with the expected board summary payload.

#### Scenario: Create board endpoint returns 201 from `AppOk`

- Given: a valid board creation request body
- When: `POST /api/boards` is executed
- Then: the route returns HTTP 201
- And: the response matches the mapped `BoardSummary` schema

#### Scenario: Create board endpoint maps `AppErr` through HTTP error mapper

- Given: command handling returns `AppErr` for a create request
- When: `POST /api/boards` is executed
- Then: the route raises through `raise_http_from_application_error`
- And: the response status and body follow API error mapping rules
