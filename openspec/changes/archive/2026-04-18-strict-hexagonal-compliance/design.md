## Context

The current `KanbanRepository` implementations (`SQLModelKanbanRepository` & `InMemoryKanbanRepository`) manage business validations (e.g. `validate_card_move`) and sequencing logic (`reorder_between_columns`) internally within methods like `update_card`. Additionally, the repository acts on individual `Card` and `Column` entities rather than treating the `Board` as an `Aggregate Root`. This violates Domain-Driven Design (DDD) rules defined in the `clean-ddd-hexagonal` standard which mandates "One repository per AGGREGATE" and clean application-level orchestration.

## Goals / Non-Goals

**Goals:**
- Decouple all domain logic (`validate_card_move`, `reorder_between_columns`, `reorder_within_column`) from the persistence adapters (`SQLModelKanbanRepository` and alternatives).
- Shift responsibility for sequence computations and validations strictly to the Command Handlers inside `src/application/commands.py`.
- Revise the `KanbanRepository` interface to be driven completely by clean parameters provided by the Application layer. The repository will do purely generic I/O.
- Relocate the repository port definitions into the domain layer (`src/domain/kanban/repository.py`).

**Non-Goals:**
- Modifying the underlying database schema (`SQLModel` table classes) or introducing database migrations.
- Rewriting the API payloads or the way controllers respond.
- Moving away from CQRS (we will keep the strict command/query separation).

## Decisions

1. **Move sequence and validation orchestration to Command Handlers**:
   - *Rationale*: Hexagonal architecture strongly dictates that the application layer coordinates infrastructure and domain. The `PatchCardHandler` will retrieve current columns from the DB, calculate validations, use the domain methods `reorder_between_columns`, and pass the exact updated states directly to the repository. The adapter will simply enact these computed updates.

2. **Move repository interface into `src/domain/kanban/`**:
   - *Rationale*: Driven ports dedicated to persistence of an Aggregate Root should reside alongside the aggregate definition as specified in the Clean Architecture skill.

3. **Restructure `update_card` interface**:
   - *Rationale*: Currently `update_card` calculates its own positions. We will update the repository's `update_card` (or create a specific sequence mechanism) that accepts the raw lists of pre-calculated card IDs and assigned column arrays, forcing it to just update the DB rows as dictated by the Use Case.

## Risks / Trade-offs

- **Risk**: Test breakage. Modifying where validation happens will likely break existing unit tests testing the repository layer.
  - **Mitigation**: Migrate validation tests from `test_sqlmodel_repository.py` to `test_commands.py` where appropriate.

- **Risk**: Complexity in `SQLModel` interactions. Moving logic outward might force us to expose more data to the application layer than before (e.g., fetching all card IDs of a column to compute sequence).
  - **Mitigation**: Provide efficient query methods on the query side to fetch the state needed for the command to make its computations quickly.
