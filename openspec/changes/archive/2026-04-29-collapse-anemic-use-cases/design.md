## Context

Every application use case is currently split into two artefacts:

- A **class** under `src/application/use_cases/<aggregate>/<verb>.py`
  declared as a `@dataclass(slots=True)` whose only method is `execute`.
- A **free function** under `src/application/commands/<aggregate>/<verb>.py`
  or `src/application/queries/<verb>.py` named `handle_<verb>` that
  contains the orchestration body.

The class's `execute` body is, in every case, a single line that
forwards arguments to the function. Example:

```12:20:src/application/use_cases/card/create_card.py
@dataclass(slots=True)
class CreateCardUseCase:
    uow: UnitOfWorkPort
    id_gen: IdGeneratorPort

    def execute(
        self, command: CreateCardCommand
    ) -> AppResult[AppCard, ApplicationError]:
        return handle_create_card(uow=self.uow, id_gen=self.id_gen, command=command)
```

The skill's "Anti-Patterns" section calls this out explicitly
(SKILL.md lines 1077–1086).

The split forces two files per use case for orchestration that fits in
one. It also doubles the surface a contributor has to navigate: the
class declares dependencies, the function uses them.

## Goals / Non-Goals

**Goals:**
- One canonical orchestration unit per use case.
- The orchestration body lives inside the use-case class's `execute`
  method, not in a separate function.
- Command and query DTOs remain co-located in their current packages
  (`src/application/commands/`, `src/application/queries/`); only the
  `handle_*` functions disappear.
- An architecture test prevents the pattern from coming back.

**Non-Goals:**
- Adding behaviour to use cases (no domain rule moves).
- Changing the API for the use cases (`execute(command_or_query)` stays).
- Changing command/query DTO types or their fields.
- Replacing the class style with a callable, a function, or a protocol.
- Touching ports, adapters, domain code, or HTTP routes.

## Decisions

### D1 — Collapse `handle_*` into `execute`; keep the class as the unit

**Decision:** for each use case, move the body of `handle_<verb>` into
the class's `execute` method. Delete the `handle_*` function. The class
remains the dependency-injection target FastAPI uses today (no change to
`src/api/dependencies/use_cases.py` shape).

After this change, `src/application/commands/<aggregate>/<verb>.py`
becomes a DTO-only module:

```python
# src/application/commands/card/create.py (after)
from dataclasses import dataclass
from datetime import datetime

from src.application.contracts import AppCardPriority


@dataclass(frozen=True, slots=True)
class CreateCardCommand:
    column_id: str
    title: str
    description: str | None
    priority: AppCardPriority
    due_at: datetime | None
```

And the use case absorbs the orchestration (assuming
`unify-domain-error-representation` already landed):

```python
# src/application/use_cases/card/create_card.py (after)
from dataclasses import dataclass

from src.application.commands.card.create import CreateCardCommand
from src.application.contracts import AppCard
from src.application.contracts.mappers import to_app_card, to_domain_priority
from src.application.kanban.errors import ApplicationError, from_domain_error
from src.application.ports.id_generator_port import IdGeneratorPort
from src.application.ports.unit_of_work_port import UnitOfWorkPort
from src.domain.kanban.errors import KanbanError
from src.domain.kanban.models import Card
from src.domain.shared.result import Err, Ok, Result


@dataclass(slots=True)
class CreateCardUseCase:
    uow: UnitOfWorkPort
    id_gen: IdGeneratorPort

    def execute(
        self, command: CreateCardCommand
    ) -> Result[AppCard, ApplicationError]:
        with self.uow:
            board_id = self.uow.lookup.find_board_id_by_column(command.column_id)
            if not board_id:
                return Err(ApplicationError.COLUMN_NOT_FOUND)

            board_result = self.uow.commands.find_by_id(board_id)
            if isinstance(board_result, Err):
                return Err(from_domain_error(board_result.error))

            board = board_result.value
            col = board.get_column(command.column_id)
            if not col:
                return Err(ApplicationError.COLUMN_NOT_FOUND)

            card = Card(
                id=self.id_gen.next_id(),
                column_id=command.column_id,
                title=command.title,
                description=command.description,
                position=0,
                priority=to_domain_priority(command.priority),
                due_at=command.due_at,
            )
            insert_result = col.insert_card(card)
            if isinstance(insert_result, Err):
                return Err(from_domain_error(insert_result.error))

            self.uow.commands.save(board)
            self.uow.commit()
            return Ok(to_app_card(card))
```

**Rationale:**

- The class is the unit FastAPI already injects via
  `Depends(get_create_card_use_case)`. Keeping it preserves the
  composition root and the architecture tests
  (`test_routes_thinness.test_route_handlers_call_exactly_one_use_case`
  asserts on `*UseCase.execute(...)` calls).
- The dataclass form (`@dataclass(slots=True)`) gives a structural
  signature for dependencies that is trivial to satisfy in tests.
- Pattern-matching on `Ok/Err` reads the same inside the class as it
  did inside the free function.
- The `handle_*` free functions only exist as a stylistic preference
  for "module-level orchestration"; they don't enable any test, mock, or
  composition that the class doesn't.

**Alternatives considered:**

- **Drop the class, keep the function.** Have FastAPI call
  `handle_create_card(uow=..., id_gen=..., command=...)` directly.
  Pros: minimal code; fewer types. Cons:
  - `src/api/dependencies/use_cases.py` would have to bind every dep
    into a `functools.partial(handle_*, uow=..., id_gen=...)` (or
    similar) for `Depends` to inject something callable. That's
    measurably uglier than the class.
  - The architecture test
    `test_route_handlers_call_exactly_one_use_case` matches on
    `*UseCase.execute(...)` calls. Removing the class would require
    rewriting that test to look for arbitrary callable invocations,
    weakening its guarantee.
  - Replacing `<Verb>UseCase` everywhere in tests, deps, and
    documentation is a larger churn than collapsing the function into
    the class.
  - Rejected.

- **Keep both, document them as alternative entry points.** Rejected:
  the user explicitly asked to fix objective gaps; SKILL.md's
  Anti-pattern 2 directly cites this shape.

### D2 — DTO files retain only command/query types

After D1, `src/application/commands/<aggregate>/<verb>.py` and
`src/application/queries/<verb>.py` become DTO-only modules. The
package `__init__.py` files keep the same public re-exports for
DTOs (`CreateCardCommand`, `GetCardQuery`, ...). Imports from
the use case modules update accordingly.

If any DTO module currently has shared helpers used only by the
`handle_*` function (audit at implementation time), those helpers
move into the use case file as private helpers prefixed with `_`.

**Alternatives considered:**

- Inline DTOs into the use case file. Rejected — the API layer
  imports DTOs to construct them in routers, and importing from
  `src.application.use_cases.card.create_card` (a nested path) feels
  worse than `src.application.commands` for that purpose.

### D3 — Architecture test enforces the new shape

Add `tests/architecture/test_use_cases_have_no_handle_passthrough.py`
(marked `@pytest.mark.architecture`) that:

1. For each module under `src/application/use_cases/`, parses the AST
   and locates classes whose name ends in `UseCase`.
2. For each such class, locates the `execute` method body.
3. Fails if `execute` consists of a single `Return` whose value is a
   `Call` to a function whose name starts with `handle_` and whose
   target lives outside the same module.

The check is intentionally narrow — it forbids the specific
pass-through shape, not legitimate calls into helpers.

Additionally, the test fails if any module under
`src/application/commands/` or `src/application/queries/` defines a
function whose name starts with `handle_`. After D1 there should be
none.

**Alternatives considered:**

- A repo-wide grep for `handle_` in CI. Rejected — too loose; would
  catch legitimate handlers if introduced in non-orchestration roles.

## Risks / Trade-offs

- **[Risk] Tests targeting `handle_*` functions break.**
  Inventory before the move (`rg "from src.application.(commands|queries).*import handle_" tests/`).
  → Mitigation: rewrite affected tests to construct the use case
  class with fake adapters and call `execute(...)`. The test surface
  becomes a class-with-fakes pattern, which is what the skill
  recommends ("use fake adapters" — SKILL.md lines 970–974).

- **[Risk] Some `handle_*` functions are imported by other
  application modules (cross-handler composition).**
  → Mitigation: an audit at the start of implementation lists all
  cross-imports between handlers. None are expected (current code
  shows clean call graphs from class → function only), but if any
  appear, the helper logic moves to a small private module under
  `src/application/use_cases/<aggregate>/_helpers.py`.

- **[Trade-off] The use case file grows from ~20 lines to ~30–60 lines.**
  Acceptable: that's where the orchestration belongs. Two files at 20
  lines each is not an improvement over one file at 50 lines.

## Migration Plan

1. **Pre-conditions:** `align-project-skeleton-to-hex-skill` and
   `unify-domain-error-representation` have landed. Result types and
   error symbols come from `src.domain.shared.result` and
   `src.application.kanban.errors`. The class collapse uses those
   imports directly.

2. **Per-aggregate migration loop** (board → card → column → health):
   For each use case file:
   - Copy the body of `handle_<verb>` into `execute`, replacing
     argument references with `self.<dep>` accesses.
   - Drop the import of `handle_<verb>` and any other symbol the
     function used that the class doesn't already need.
   - Delete `handle_<verb>` from the corresponding `commands/` or
     `queries/` module.
   - Update the module-level `__init__.py` re-exports if they exposed
     the function.
   - Run `uv run pytest tests/unit -k <aggregate>` until green.

3. **Test rewrite:** for any test importing `handle_*`, rewrite it to
   instantiate the use case class with fakes/mocks and call
   `execute(...)`.

4. **Add architecture test (D3).** Verify it passes against the cleaned
   tree; manually reintroduce a violation locally to confirm it fails;
   revert.

5. **Verification:** full matrix —
   `uv run pytest tests/architecture -m architecture`,
   `uv run pytest tests/unit`, `uv run pytest tests/integration`,
   `uv run pytest tests/e2e`, `uv run lint-imports`, `uv run mypy`.

**Rollback:** revert the change PR. No data, schema, or HTTP contract
involvement.

## Open Questions

- After D1, several files in `src/application/commands/<aggregate>/`
  may shrink to only the DTO definition. If any aggregate ends up with
  a single one-class file per command, consider consolidating the
  aggregate's command DTOs into a single file. This is **out of scope**
  for this change but worth noting as a follow-up.
- For `handle_health_check`, which returns `bool` rather than a
  Result, the collapsed `execute` keeps the same return type.
  No special handling needed.
