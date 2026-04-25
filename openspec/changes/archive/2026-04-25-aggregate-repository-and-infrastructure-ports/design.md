# Design: Aggregate-Level Repository Interface and Infrastructure Ports

**Change ID**: `aggregate-repository-and-infrastructure-ports`

---

## Core Decision: What a Repository Should Express

A repository port's vocabulary should be **persistence-neutral aggregate operations**, not business operations. The distinction:

| Business operation (wrong for port) | Aggregate persistence primitive (correct for port) |
|---|---|
| `create_board(title)` | `save(board)` |
| `update_board(board_id, title)` | `save(board)` (after mutation in domain) |
| `delete_board(board_id)` | `remove(board_id)` |
| `get_board(board_id)` | `find_by_id(board_id)` |

With this interface, the port says: "I need to store and retrieve Board aggregates, and delete them by ID." It does not say anything about titles or business state.

---

## Architectural Decision Records

### ADR-1: `save()` is infallible — database failures propagate as exceptions

**Decision**: `save(board: Board) -> None` — no `Result` wrapper.

**Rationale**: `Result` types represent **business errors** (entity not found, business rule violated). A `save` failure is an **infrastructure failure** (database connection lost, constraint violation due to data inconsistency) — not a business error. These are exceptional conditions, not recoverable domain states. They must propagate as exceptions and become HTTP 500 responses via the global exception handler in `src/api/error_handlers.py`. Wrapping them in `Result` would force every call site to handle an error that cannot be meaningfully surfaced to the caller as a business error.

**Consequence**: `handle_create_board` and `handle_patch_board` do not check a Result from `self.uow.kanban.save(...)`. If save raises an exception, it propagates upward and becomes a 500.

**Counter-argument considered**: Making `save` fallible allows tests to simulate save failures. **Rejected**: tests that need to simulate infrastructure failures should use integration tests with a real database, not fake port behavior.

### ADR-2: `find_board_id_by_card` and `find_board_id_by_column` remain on the command port

**Decision**: Both lookup methods stay on `KanbanCommandRepositoryPort` despite being read operations.

**Rationale**: Command handlers follow a read-then-write pattern — they look up the board ID to load the aggregate before mutating it. These lookups happen **inside the UoW transaction scope** (same database session). Routing them through the query repository would open a separate session, creating transaction isolation issues. The lookup methods are scoped to the command repository because they serve command execution, not query results.

**Alternative considered**: Separate `BoardLookupPort` on the UoW. **Rejected**: adds a port for two methods whose only consumer is the command handler, and introduces a third dependency on the UoW. Premature abstraction.

### ADR-3: `AppBoardSummary` inline construction in command handlers — no dedicated mapper

**Decision**: `handle_create_board` constructs `AppBoardSummary` inline from `Board` fields. No `to_app_board_summary_from_board` function.

**Rationale**: The mapping is three fields (`id`, `title`, `created_at`). A dedicated mapper function adds indirection for a trivial operation. Inline construction `AppBoardSummary(id=board.id, title=board.title, created_at=board.created_at)` is self-documenting and has zero abstraction cost.

---

## Revised Port Surfaces

### `KanbanCommandRepositoryPort`

```python
# src/application/ports/kanban_command_repository.py
from __future__ import annotations
from typing import Protocol
from src.domain.kanban.models import Board
from src.domain.shared.errors import KanbanError
from src.domain.shared.result import Result

class KanbanCommandRepositoryPort(Protocol):
    def save(self, board: Board) -> None: ...                          # infallible — see ADR-1
    def find_by_id(self, board_id: str) -> Result[Board, KanbanError]: ...
    def remove(self, board_id: str) -> Result[None, KanbanError]: ...
    def find_board_id_by_card(self, card_id: str) -> str | None: ...  # see ADR-2
    def find_board_id_by_column(self, column_id: str) -> str | None: ...  # see ADR-2
```

### `KanbanQueryRepositoryPort`

> **Sequencing note**: After this change, `list_all()` returns `list[BoardSummary]` where `BoardSummary` is still the domain type. Change `relocate-boardsummary-read-model` subsequently updates the return type to `list[AppBoardSummary]` and removes the domain `BoardSummary`. Apply changes in order.

```python
# src/application/ports/kanban_query_repository.py
from __future__ import annotations
from typing import Protocol
from src.domain.kanban.models import Board, BoardSummary
from src.domain.shared.errors import KanbanError
from src.domain.shared.result import Result

class KanbanQueryRepositoryPort(Protocol):
    def list_all(self) -> list[BoardSummary]: ...   # updated to AppBoardSummary in Change 10
    def find_by_id(self, board_id: str) -> Result[Board, KanbanError]: ...
    def find_board_id_by_card(self, card_id: str) -> str | None: ...
```

### `IdGenerator` port

```python
# src/application/ports/id_generator.py
from __future__ import annotations
from typing import Protocol

class IdGenerator(Protocol):
    def next_id(self) -> str: ...
```

### `Clock` port

```python
# src/application/ports/clock.py
from __future__ import annotations
from datetime import datetime
from typing import Protocol

class Clock(Protocol):
    def now(self) -> datetime: ...
```

---

## Infrastructure Adapters

### `UUIDIdGenerator`

```python
# src/infrastructure/adapters/uuid_id_generator.py
from __future__ import annotations
import uuid

class UUIDIdGenerator:
    def next_id(self) -> str:
        return str(uuid.uuid4())
```

### `SystemClock`

```python
# src/infrastructure/adapters/system_clock.py
from __future__ import annotations
from datetime import datetime, timezone

class SystemClock:
    def now(self) -> datetime:
        return datetime.now(timezone.utc)
```

---

## Revised `KanbanCommandHandlers`

The handlers construct domain entities using `id_gen` and `clock`. `save()` is called without result-checking (ADR-1).

```python
@dataclass(slots=True)
class KanbanCommandHandlers(KanbanCommandInputPort):
    uow: UnitOfWork
    id_gen: IdGenerator
    clock: Clock

    def handle_create_board(self, command: CreateBoardCommand) -> AppResult[AppBoardSummary, ApplicationError]:
        board = Board(
            id=self.id_gen.next_id(),
            title=command.title,
            created_at=self.clock.now(),
        )
        with self.uow:
            self.uow.kanban.save(board)                    # infallible — see ADR-1
            self.uow.commit()
            return AppOk(AppBoardSummary(                  # inline construction — see ADR-3
                id=board.id,
                title=board.title,
                created_at=board.created_at,
            ))

    def handle_patch_board(self, command: PatchBoardCommand) -> AppResult[AppBoardSummary, ApplicationError]:
        with self.uow:
            result = self.uow.kanban.find_by_id(command.board_id)
            if isinstance(result, Err):
                return AppErr(from_domain_error(result.error))
            board = result.value
            board.title = command.title
            self.uow.kanban.save(board)                    # infallible — see ADR-1
            self.uow.commit()
            return AppOk(AppBoardSummary(
                id=board.id,
                title=board.title,
                created_at=board.created_at,
            ))

    def handle_delete_board(self, command: DeleteBoardCommand) -> AppResult[None, ApplicationError]:
        with self.uow:
            result = self.uow.kanban.remove(command.board_id)
            if isinstance(result, Err):
                return AppErr(from_domain_error(result.error))
            self.uow.commit()
            return AppOk(None)
```

> **Note on `handle_create_board` return type**: The port signature (`-> AppResult`) and the router pattern-match are finalized in change `normalize-command-handler-contracts`. Apply that change after this one.

---

## Revised `SQLModelKanbanRepository` (Key Method Changes)

```python
def save(self, board: Board) -> None:
    # Full upsert: inserts if board.id not in DB, updates if present.
    # Raises exception on DB errors — intentional, see ADR-1.
    ...

def find_by_id(self, board_id: str) -> Result[Board, KanbanError]:
    # replaces get_board — same implementation
    ...

def remove(self, board_id: str) -> Result[None, KanbanError]:
    # replaces delete_board — same implementation
    ...
```

---

## Fake Adapters for Tests

```python
# tests/support/fakes.py
from datetime import datetime

class FakeIdGenerator:
    """Returns pre-loaded IDs in sequence; falls back to unique counter-based IDs."""
    def __init__(self, *ids: str) -> None:
        self._ids = list(ids)
        self._counter = 0

    def next_id(self) -> str:
        if self._ids:
            return self._ids.pop(0)
        self._counter += 1
        # Zero-pad counter in the node field of a UUID4-shaped string
        return f"00000000-0000-4000-8000-{self._counter:012d}"


class FakeClock:
    def __init__(self, fixed: datetime) -> None:
        self._fixed = fixed

    def now(self) -> datetime:
        return self._fixed
```

> **Why counter-based IDs**: A hard-coded constant default would produce the same ID for every call on the same generator instance. A single test that creates a board, a column, and a card would assign the same ID to all three, causing collisions. The counter ensures each `next_id()` call returns a unique string.

---

## DI Composition Update

```python
# src/infrastructure/config/di/composition.py (additions)
from src.infrastructure.adapters.uuid_id_generator import UUIDIdGenerator
from src.infrastructure.adapters.system_clock import SystemClock

@dataclass(frozen=True, slots=True)
class RuntimeDependencies:
    repository: ManagedKanbanRepositoryPort
    uow_factory: UnitOfWorkFactory
    readiness_probe: ReadinessProbe
    id_gen: IdGenerator   # added
    clock: Clock          # added
    shutdown: ShutdownHook
```

```python
# src/infrastructure/config/di/container.py (update)
command_handlers_factory=lambda: KanbanCommandHandlers(
    uow=runtime.uow_factory(),
    id_gen=runtime.id_gen,
    clock=runtime.clock,
),
```
