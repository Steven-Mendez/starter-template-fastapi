# Spec: Aggregate Repository Interface and Infrastructure Ports

**Capability**: repository-port
**Change**: aggregate-repository-and-infrastructure-ports

---

## ADDED Requirements

### Requirement: RP-02 — `IdGenerator` port in application layer

The system MUST satisfy this requirement as specified below.


**Priority**: High

An `IdGenerator` Protocol lives in `src/application/ports/id_generator.py` and provides deterministic ID generation for application-layer entity construction.

**Acceptance Criteria**:
1. `src/application/ports/id_generator.py` exists with `IdGenerator(Protocol)` containing `next_id() -> str`.
2. `src/infrastructure/adapters/uuid_id_generator.py` exists with `UUIDIdGenerator` implementing `IdGenerator`.
3. `UUIDIdGenerator().next_id()` returns a valid UUID4 string.
4. `FakeIdGenerator` in `tests/support/fakes.py` implements `IdGenerator` and returns pre-specified IDs.
5. `KanbanCommandHandlers` declares `id_gen: IdGenerator` as a constructor field.
6. No direct `uuid.uuid4()` call exists inside `KanbanCommandHandlers`.

#### Scenario: Handlers use fake ID generator in tests

- Given: `KanbanCommandHandlers` wired with `FakeIdGenerator(["board-id-1"])`
- When: `handle_create_board(CreateBoardCommand(title="Test"))` is called
- Then: the returned `AppBoardSummary.id` equals `"board-id-1"`

#### Scenario: Production handlers use UUID generator

- Given: `KanbanCommandHandlers` wired with `UUIDIdGenerator()`
- When: `handle_create_board` is called
- Then: the returned board ID is a valid UUID4 string

### Requirement: RP-03 — `Clock` port in application layer

The system MUST satisfy this requirement as specified below.


**Priority**: High

A `Clock` Protocol lives in `src/application/ports/clock.py` so that timestamp generation is fakeable in tests without monkeypatching.

**Acceptance Criteria**:
1. `src/application/ports/clock.py` exists with `Clock(Protocol)` containing `now() -> datetime`.
2. `src/infrastructure/adapters/system_clock.py` exists with `SystemClock` implementing `Clock`.
3. `SystemClock().now()` returns a timezone-aware UTC datetime.
4. `FakeClock` in `tests/support/fakes.py` implements `Clock` and returns a fixed `datetime`.
5. `KanbanCommandHandlers` declares `clock: Clock` as a constructor field.
6. No direct `datetime.now()` call exists inside `KanbanCommandHandlers`.

#### Scenario: Handlers use fake clock in tests

- Given: `KanbanCommandHandlers` wired with `FakeClock(datetime(2024, 1, 1, tzinfo=timezone.utc))`
- When: `handle_create_board(CreateBoardCommand(title="Test"))` is called
- Then: the returned `AppBoardSummary.created_at` equals `datetime(2024, 1, 1, tzinfo=timezone.utc)`

## ADDED Requirements

### Requirement: RP-01 — Command repository port exposes aggregate persistence primitives only


**Priority**: Critical

`KanbanCommandRepositoryPort` MUST expose only aggregate-level persistence operations. It MUST not expose methods that encode business operations by name.

**Acceptance Criteria**:
1. `KanbanCommandRepositoryPort` contains `save(board: Board)`, `find_by_id(board_id: str)`, `remove(board_id: str)`.
2. `KanbanCommandRepositoryPort` does not contain `create_board`, `update_board`, or `delete_board`.
3. Both `SQLModelKanbanRepository` and `InMemoryKanbanRepository` structurally satisfy `KanbanCommandRepositoryPort`.
4. The `test_persistence_adapters_match_repository_port_surface` test passes with the new method names.

#### Scenario: Adapter conforms to the revised port

- Given: `SQLModelKanbanRepository` after refactor
- When: it is type-checked as `KanbanCommandRepositoryPort`
- Then: no type error is raised

#### Scenario: Old business-operation methods are absent

- Given: `KanbanCommandRepositoryPort` definition
- When: its public methods are enumerated
- Then: `create_board`, `update_board`, and `delete_board` are not present

### Requirement: RP-04 — `KanbanCommandHandlers` constructs domain entities, does not delegate construction to repository


**Priority**: Critical

The application command handler MUST construct domain entities (`Board`, `Column`, `Card`) using `IdGenerator` and `Clock` ports, then pass the constructed entity to the repository for persistence.

**Acceptance Criteria**:
1. `handle_create_board` constructs a `Board` instance before calling any repository method.
2. The repository's `save(board)` receives a fully-constructed `Board` entity.
3. No repository method in `KanbanCommandRepositoryPort` accepts a bare title string to create an entity.
4. `handle_create_column` uses `self.id_gen.next_id()` for column ID.
5. `handle_create_card` uses `self.id_gen.next_id()` for card ID.

#### Scenario: Board construction precedes persistence

- Given: `KanbanCommandHandlers` with fakes
- When: `handle_create_board(CreateBoardCommand(title="My Board"))` is called
- Then: `uow.kanban.save` is called with a `Board` whose `title == "My Board"`, `id` comes from `id_gen`, and `created_at` comes from `clock`
- And: no repository method named `create_board` is called

### Requirement: RP-05 — `save(board)` implements full upsert semantics


**Priority**: High

`KanbanCommandRepositoryPort.save(board)` MUST handle both creation of a new board and updating an existing board. Both `SQLModelKanbanRepository` and `InMemoryKanbanRepository` MUST implement this.

**Acceptance Criteria**:
1. Calling `save(board)` for a board whose ID does not exist in the store inserts it.
2. Calling `save(board)` for a board whose ID already exists updates it.
3. The repository contract test verifies both creation and update via `save`.

#### Scenario: First save creates the board

- Given: an empty repository
- When: `save(Board(id="new-id", title="Fresh", created_at=...))` is called
- Then: `find_by_id("new-id")` returns `Ok(board)` with `title == "Fresh"`

#### Scenario: Second save updates the board

- Given: a repository containing board with id `"b1"` and title `"Original"`
- When: `save(Board(id="b1", title="Updated", ...))` is called
- Then: `find_by_id("b1")` returns `Ok(board)` with `title == "Updated"`
