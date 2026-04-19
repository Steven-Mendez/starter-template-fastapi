## 1. Domain Object Refactoring

- [x] 1.1 Transform `Board` and `Card` from anemic `@dataclass` objects into rich entities with internal validations.
- [x] 1.2 Move mapping semantics and `validate_card_move` / `reorder` logic into aggregate methods instead of standalone services.

## 2. Unit of Work Abstraction

- [x] 2.1 Define the `UnitOfWork` protocol inside `src/application/shared/unit_of_work.py`.
- [x] 2.2 Implement `SqlModelUnitOfWork` utilizing SQLAlchemy sessions.
- [x] 2.3 Implement `InMemoryUnitOfWork` for tests.

## 3. Repository Scope Reduction

- [x] 3.1 Modify `KanbanCommandRepository` to only expose operations at the `Board` aggregate level (remove granular `update_card`, `create_column`, etc).
- [x] 3.2 Implement `board` aggregate serialization logic inside the respective SQLModel and InMemory adapters.

## 4. Command Handlers Upgrades

- [x] 4.1 Update `KanbanCommandHandlers` to wrap all mutations entirely inside a `with uow:` block to guarantee ACID properties.
- [x] 4.2 Replace procedural repository calls with Aggregate method invocations prior to tracking changes in the UOW.
- [x] 4.3 Remove unused `KanbanUseCases` from `src/application/use_cases/kanban.py` to fix layering ambiguity.
