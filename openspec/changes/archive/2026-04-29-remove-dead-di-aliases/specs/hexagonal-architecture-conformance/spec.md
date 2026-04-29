## ADDED Requirements

### Requirement: DI module exposes a single canonical name per concept

The DI package `src/infrastructure/config/di/` SHALL declare exactly one
public name for each concept it exposes. It SHALL NOT carry
"backward-compatible" aliases when there are no production consumers
that would break by removal. Each concept's canonical name SHALL be the
one whose body contains the actual implementation; thin wrappers
created solely to preserve a legacy import path SHALL be removed.

#### Scenario: no `repository` alias on the container
- **WHEN** a contributor inspects `ConfiguredAppContainer`
- **THEN** there is no `repository` property; consumers access
  `container.repositories.kanban` directly

#### Scenario: no `create_repository_for_settings` helper
- **WHEN** a contributor inspects
  `src/infrastructure/config/di/composition.py`
- **THEN** there is no `create_repository_for_settings` function;
  consumers call `create_kanban_repository_for_settings(settings)`
  directly

#### Scenario: DI `__all__` lists each name once
- **WHEN** `src/infrastructure/config/di/__init__.py` is inspected
- **THEN** every entry in `__all__` is the canonical name of its
  concept; no entry is documented as a wrapper or alias

### Requirement: Architecture test forbids backward-compatible aliases without consumers

The `tests/architecture/` suite SHALL include a test, marked
`@pytest.mark.architecture`, that fails if any class, function, method,
or property declared under `src/infrastructure/config/di/` has a
docstring containing the phrase "backward-compatible" (case-insensitive)
unless every consumer of that symbol can be located under `src/`
(production code, not tests only).

#### Scenario: alias documented as backward-compatible without production consumers fails the suite
- **WHEN** a contributor adds a property whose docstring says
  "backward-compatible" and the only consumers live under `tests/`
- **THEN** running `uv run pytest tests/architecture -m architecture`
  exits non-zero with a failure that names the offending symbol

#### Scenario: legitimate compatibility shim with production consumers passes
- **WHEN** a future change introduces a deprecated alias that production
  code under `src/` still calls, and the docstring is updated to point
  at the canonical replacement
- **THEN** the architecture test passes (the rule fails only when there
  are zero production consumers)
