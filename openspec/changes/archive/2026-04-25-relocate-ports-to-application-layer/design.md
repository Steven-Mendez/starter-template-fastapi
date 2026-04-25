# Design: Relocate Repository Ports to the Application Layer

**Change ID**: `relocate-ports-to-application-layer`

---

## Architectural Decision

### Why Ports Belong in Application, Not Domain

Hexagonal architecture defines two kinds of ports:

- **Driving ports** (inbound): interfaces through which the outside world calls the application (e.g., `KanbanCommandInputPort`, `KanbanQueryInputPort`). These are already correctly placed in `src/application/commands/port.py` and `src/application/queries/port.py`.
- **Driven ports** (outbound): interfaces the application calls to reach external systems (e.g., repositories, email senders, clocks). These must live in `src/application/ports/` so the application layer owns both ends of its contract surface.

The domain layer must not know that a persistence boundary exists. Domain entities (`Board`, `Column`, `Card`) define business behavior. The application layer orchestrates use cases by calling domain objects and then delegating I/O through driven ports. The ports are the application's vocabulary for what it needs — not the domain's.

Current (incorrect) dependency graph fragment:
```
src.infrastructure.persistence.sqlmodel_repository
  → src.domain.kanban.repository.KanbanRepositoryPort   ← port in wrong layer
  → src.domain.kanban.models.Board

src.application.shared.unit_of_work
  → src.domain.kanban.repository.command.KanbanCommandRepositoryPort  ← port in wrong layer
```

Target dependency graph fragment:
```
src.infrastructure.persistence.sqlmodel_repository
  → src.application.ports.kanban_repository.KanbanRepositoryPort     ← port in correct layer
  → src.domain.kanban.models.Board

src.application.shared.unit_of_work
  → src.application.ports.kanban_command_repository.KanbanCommandRepositoryPort  ← correct
```

---

## Target File Structure

```
src/
  application/
    ports/
      __init__.py
        # re-exports: KanbanCommandRepositoryPort, KanbanQueryRepositoryPort, KanbanRepositoryPort
      kanban_command_repository.py
        # Protocol: KanbanCommandRepositoryPort
        # Methods: create_board, update_board, delete_board, get_board,
        #          save_board, find_board_id_by_card, find_board_id_by_column
      kanban_query_repository.py
        # Protocol: KanbanQueryRepositoryPort
        # Methods: list_boards, get_board, find_board_id_by_card
      kanban_repository.py
        # Protocol: KanbanRepositoryPort(KanbanQueryRepositoryPort, KanbanCommandRepositoryPort)
    commands/
      handlers.py      # updated imports
      port.py          # unchanged
    queries/
      handlers.py      # updated imports
      port.py          # unchanged
    shared/
      unit_of_work.py  # updated imports
```

---

## Port Method Signatures (Unchanged)

`KanbanCommandRepositoryPort`:

```python
from typing import Protocol
from src.domain.kanban.models import Board, BoardSummary
from src.domain.shared.errors import KanbanError
from src.domain.shared.result import Result

class KanbanCommandRepositoryPort(Protocol):
    def create_board(self, title: str) -> BoardSummary: ...
    def update_board(self, board_id: str, title: str) -> Result[BoardSummary, KanbanError]: ...
    def delete_board(self, board_id: str) -> Result[None, KanbanError]: ...
    def get_board(self, board_id: str) -> Result[Board, KanbanError]: ...
    def save_board(self, board: Board) -> Result[None, KanbanError]: ...
    def find_board_id_by_card(self, card_id: str) -> str | None: ...
    def find_board_id_by_column(self, column_id: str) -> str | None: ...
```

> **Note:** The method signatures on these ports are not changed in this change — they are relocated as-is. Refactoring the port interface (removing business-operation methods, adding aggregate primitives) is handled by the separate change `aggregate-repository-and-infrastructure-ports`.

`KanbanQueryRepositoryPort`:

```python
from typing import Protocol
from src.domain.kanban.models import Board, BoardSummary
from src.domain.shared.errors import KanbanError
from src.domain.shared.result import Result

class KanbanQueryRepositoryPort(Protocol):
    def list_boards(self) -> list[BoardSummary]: ...
    def get_board(self, board_id: str) -> Result[Board, KanbanError]: ...
    def find_board_id_by_card(self, card_id: str) -> str | None: ...
```

`KanbanRepositoryPort`:

```python
from typing import Protocol
from src.application.ports.kanban_command_repository import KanbanCommandRepositoryPort
from src.application.ports.kanban_query_repository import KanbanQueryRepositoryPort

class KanbanRepositoryPort(
    KanbanQueryRepositoryPort,
    KanbanCommandRepositoryPort,
    Protocol,
):
    pass
```

---

## Import Update Map

| Old import path | New import path |
|---|---|
| `from src.domain.kanban.repository import KanbanRepositoryPort` | `from src.application.ports.kanban_repository import KanbanRepositoryPort` |
| `from src.domain.kanban.repository.command import KanbanCommandRepositoryPort` | `from src.application.ports.kanban_command_repository import KanbanCommandRepositoryPort` |
| `from src.domain.kanban.repository.query import KanbanQueryRepositoryPort` | `from src.application.ports.kanban_query_repository import KanbanQueryRepositoryPort` |
| `from src.domain.kanban.repository import KanbanCommandRepositoryPort` | `from src.application.ports import KanbanCommandRepositoryPort` |

---

## Boundary Test Changes

`DENY_MATRIX` in `test_hexagonal_boundaries.py` must be updated:

```python
# Before (infrastructure was allowed to import from domain.kanban.repository because ports lived there)
# No explicit allowance existed, but the graph traversal did not flag it because
# domain is allowed to be imported by infrastructure.

# After: add an assertion that src.domain.kanban.repository does not exist as a module
def test_domain_does_not_contain_port_modules() -> None:
    port_dir = SRC_DIR / "domain" / "kanban" / "repository"
    assert not port_dir.exists(), (
        "Repository ports must not live in the domain layer. "
        "Expected location: src/application/ports/"
    )
```

---

## Sequencing

This change is a prerequisite for `aggregate-repository-and-infrastructure-ports`. Complete the relocation first, then refactor the port interface in the next change. Attempting both simultaneously creates a larger, harder-to-review diff.
