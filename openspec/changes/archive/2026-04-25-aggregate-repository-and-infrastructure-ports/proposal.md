# Proposal: Aggregate-Level Repository Interface and Infrastructure Ports

**Change ID**: `aggregate-repository-and-infrastructure-ports`
**Priority**: Critical
**Status**: Proposed
**Depends on**: `relocate-ports-to-application-layer`

---

## Problem Statement

The current `KanbanCommandRepositoryPort` exposes methods named after **business operations** (`create_board`, `update_board`, `delete_board`) rather than **aggregate persistence primitives** (`save`, `find_by_id`, `remove`). This creates two compounding problems:

### Problem A: Business logic embedded in the persistence port

`create_board(title: str) -> BoardSummary` is a business operation — it names, constructs, and persists an aggregate — yet it lives inside the persistence contract. As a consequence, ID generation (`uuid.uuid4()`) and timestamp creation (`datetime.now(timezone.utc)`) happen **inside the SQLModel repository adapter**, which is infrastructure code. Infrastructure is deciding the identity and creation time of domain entities. This inverts the correct ownership: the domain (or application, using infrastructure ports) should construct entities.

Concrete evidence in `sqlmodel_repository.py`:
```python
def create_board(self, title: str) -> BoardSummary:
    board = BoardTable(
        id=str(uuid.uuid4()),         # ID generated in infrastructure
        title=title,
        created_at=datetime.now(timezone.utc),  # timestamp generated in infrastructure
    )
```

### Problem B: No `IdGenerator` or `Clock` port abstractions

Because ID and timestamp generation happen in infrastructure, the application layer has no way to control or fake these in tests. The `handle_create_column` and `handle_create_card` command handlers call `uuid.uuid4()` directly:
```python
column = Column(
    id=str(uuid.uuid4()),   # coupled to uuid library, not fakeable via port
    ...
)
```
There is no `IdGenerator` port or `Clock` port, so tests cannot produce deterministic IDs or timestamps without monkeypatching.

---

## Rationale

Per `hex-design-guide.md`:
> Application code depends on domain code and port interfaces. Infrastructure depends on application/domain contracts.

The repository should be a **persistence boundary**, not a **factory**. Creating a domain aggregate is an application-layer responsibility, optionally guided by domain factories. Persisting a created aggregate is the repository's responsibility.

Correct flow:
```
application handler
  → id_gen.next_id() via IdGenerator port
  → clock.now() via Clock port
  → Board.new(id, title, created_at)   ← entity construction in app/domain layer
  → repository.save(board)             ← pure persistence operation
```

Current (broken) flow:
```
application handler
  → repository.create_board(title)     ← business operation + ID + persistence all in one
```

---

## Scope

**In scope:**
- Rename/replace `create_board`, `update_board`, `delete_board` in `KanbanCommandRepositoryPort` with aggregate-level methods: `save(board)`, `find_by_id(board_id)`, `remove(board_id)`.
- Add `IdGenerator` port to `src/application/ports/id_generator.py`.
- Add `Clock` port to `src/application/ports/clock.py`.
- Add `UUIDIdGenerator` adapter to `src/infrastructure/adapters/uuid_id_generator.py`.
- Add `SystemClock` adapter to `src/infrastructure/adapters/system_clock.py`.
- Refactor `KanbanCommandHandlers` to construct domain entities using `IdGenerator` and `Clock`.
- Refactor `SQLModelKanbanRepository` to implement the new port surface.
- Refactor `InMemoryKanbanRepository` to implement the new port surface.
- Add `id_gen` and `clock` to the DI composition root.
- Update `KanbanQueryRepositoryPort` to rename `get_board` to `find_by_id` (consistency).

**Out of scope:**
- Adding `Board.new()` factory classmethod (recommended but separate concern).
- `BoardSummary` relocation (addressed separately).
- Async conversion.
- Domain events.

---

## Affected Modules

| File | Change |
|---|---|
| `src/application/ports/kanban_command_repository.py` | Modified — new method signatures |
| `src/application/ports/kanban_query_repository.py` | Modified — rename `get_board` → `find_by_id` |
| `src/application/ports/id_generator.py` | Added |
| `src/application/ports/clock.py` | Added |
| `src/application/commands/handlers.py` | Modified — uses IdGenerator, Clock, new repo API |
| `src/application/shared/unit_of_work.py` | Modified — if UoW exposes repo, update method names |
| `src/infrastructure/persistence/sqlmodel_repository.py` | Modified — implement new port surface |
| `src/infrastructure/persistence/in_memory_repository.py` | Modified — implement new port surface |
| `src/infrastructure/adapters/uuid_id_generator.py` | Added |
| `src/infrastructure/adapters/system_clock.py` | Added |
| `src/infrastructure/config/di/composition.py` | Modified — wire IdGenerator, Clock |
| `src/infrastructure/config/di/container.py` | Modified — pass id_gen, clock to handlers |
| `tests/unit/test_kanban_command_handlers.py` | Modified — use fake id_gen and clock |
| `tests/unit/test_kanban_repository_contract.py` | Modified — call new port methods |
| `tests/unit/test_kanban_store.py` | Heavily modified or deleted — calls `update_board`, `delete_board`, `save_board` which will no longer exist |
| `tests/support/kanban_builders.py` | Modified — `KanbanBuilderRepository` protocol uses old method names; `StoreBuilder` calls `create_board`, `get_board`, `save_board` |

---

## Proposed Port Interface

```python
# src/application/ports/kanban_command_repository.py
from typing import Protocol
from src.domain.kanban.models import Board, BoardSummary
from src.domain.shared.errors import KanbanError
from src.domain.shared.result import Result

class KanbanCommandRepositoryPort(Protocol):
    def save(self, board: Board) -> Result[None, KanbanError]: ...
    def find_by_id(self, board_id: str) -> Result[Board, KanbanError]: ...
    def remove(self, board_id: str) -> Result[None, KanbanError]: ...
    def find_board_id_by_card(self, card_id: str) -> str | None: ...
    def find_board_id_by_column(self, column_id: str) -> str | None: ...

# src/application/ports/id_generator.py
from typing import Protocol
class IdGenerator(Protocol):
    def next_id(self) -> str: ...

# src/application/ports/clock.py
from typing import Protocol
from datetime import datetime
class Clock(Protocol):
    def now(self) -> datetime: ...
```

---

## Acceptance Criteria

1. `KanbanCommandRepositoryPort` contains no method named `create_board`, `update_board`, or `delete_board`.
2. `KanbanCommandRepositoryPort` contains `save`, `find_by_id`, and `remove`.
3. `src/application/ports/id_generator.py` defines `IdGenerator(Protocol)` with `next_id() -> str`.
4. `src/application/ports/clock.py` defines `Clock(Protocol)` with `now() -> datetime`.
5. `KanbanCommandHandlers` constructor accepts `uow`, `id_gen: IdGenerator`, `clock: Clock`.
6. `KanbanCommandHandlers.handle_create_board` constructs a `Board` domain object and calls `uow.kanban.save(board)`.
7. No call to `uuid.uuid4()` or `datetime.now()` exists directly in `KanbanCommandHandlers`.
8. `SQLModelKanbanRepository` and `InMemoryKanbanRepository` implement the updated port surface.
9. All existing tests pass. New unit tests for `handle_create_board` use a fake `IdGenerator` and fake `Clock` to assert deterministic IDs and timestamps.

---

## Migration Strategy

1. Complete `relocate-ports-to-application-layer` first.
2. Update `KanbanCommandRepositoryPort` in the new location with the new method signatures.
3. Update `KanbanQueryRepositoryPort` to rename `get_board` → `find_by_id`.
4. Create `IdGenerator` and `Clock` port files.
5. Create `UUIDIdGenerator` and `SystemClock` infrastructure adapters.
6. Refactor `SQLModelKanbanRepository`: implement `save`, `find_by_id`, `remove`; remove `create_board`, `update_board`, `delete_board`.
7. Refactor `InMemoryKanbanRepository` similarly.
8. Refactor `KanbanCommandHandlers` to accept `id_gen` and `clock`, construct entities, call new port methods.
9. Update DI composition to wire the two new adapters.
10. Update all tests.

---

## Risks and Tradeoffs

| Risk | Mitigation |
|---|---|
| `BoardSummary` was returned by `create_board`; after refactor there's no direct return from `save` | `handle_create_board` constructs the entity before calling `save`, so it already has the data needed to return `AppBoardSummary`. No information is lost. |
| Two-step `find_by_id` + `save` per operation may seem more I/O than combined `create_board` | The repository `find_by_id` call in the SQL adapter is a single indexed PK lookup. Cost is negligible and the gain in testability and correctness outweighs it. |
| Existing contract tests test old method names | Update the contract test suite in `test_kanban_repository_contract.py` to call the new methods. |

---

## Test Strategy

- Add `FakeIdGenerator` and `FakeClock` to `tests/support/`.
- In `test_kanban_command_handlers.py`, construct `KanbanCommandHandlers(uow=..., id_gen=FakeIdGenerator("fixed-id"), clock=FakeClock(fixed_dt))`.
- Assert that created entities have the IDs and timestamps supplied by the fake ports.
- Repository contract tests call `save(board)`, `find_by_id(id)`, `remove(id)` to verify both adapters comply.
