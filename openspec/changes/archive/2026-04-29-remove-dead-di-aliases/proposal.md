## Why

Two surfaces inside `src/infrastructure/config/di/` are documented in their
own docstrings as "backward-compatible" but have no production consumers —
only tests written specifically against them:

```36:39:src/infrastructure/config/di/container.py
    @property
    def repository(self) -> ManagedKanbanRepositoryPort:
        """Backward-compatible alias to the kanban repository."""
        return self.repositories.kanban
```

```70:74:src/infrastructure/config/di/composition.py
def create_repository_for_settings(
    settings: AppSettings,
) -> ManagedKanbanRepositoryPort:
    """Backward-compatible helper for callers expecting a single repository."""
    return create_kanban_repository_for_settings(settings)
```

`rg "container\.repository|create_repository_for_settings"` confirms the only
consumers are `tests/unit/test_lifespan.py:20` and
`tests/unit/test_repository_selection.py:9,19,31`. No module under `src/`
calls either symbol. For a starter template there is no prior version to be
backward-compatible with, so these aliases are dead surface masquerading as
public API. They also force the DI public surface (`__init__.py`) to expose
two names per concept (`create_kanban_repository_for_settings` AND
`create_repository_for_settings`).

The skill states architecture should "control complexity, not hide simplicity"
(SKILL.md lines 1043–1048). These aliases hide simplicity.

## What Changes

- Remove the `repository` property from `ConfiguredAppContainer`
  (`src/infrastructure/config/di/container.py`).
- Remove the `create_repository_for_settings` function from
  `src/infrastructure/config/di/composition.py`.
- Remove their re-exports from `src/infrastructure/config/di/__init__.py`
  (`__all__` and the import statement).
- Rewrite `tests/unit/test_lifespan.py` and
  `tests/unit/test_repository_selection.py` to use the canonical names that
  already exist:
  - `container.repositories.kanban` instead of `container.repository`.
  - `create_kanban_repository_for_settings(settings)` instead of
    `create_repository_for_settings(settings)`.
- Add an architecture test under `tests/architecture/` that fails if any
  symbol declared in `src/infrastructure/config/di/` carries the term
  "backward-compatible" in its docstring.

No production code changes (no module under `src/` references either
removed symbol). No HTTP / DB / domain / application surface changes.

## Capabilities

### New Capabilities
<!-- None. -->

### Modified Capabilities
- `hexagonal-architecture-conformance`: adds a requirement that the DI
  module exposes a single canonical name per concept and forbids
  "backward-compatible" aliases without production consumers. Depends on
  `align-project-skeleton-to-hex-skill` having landed first.

## Impact

- Affected code:
  - `src/infrastructure/config/di/container.py` (remove `repository`
    property).
  - `src/infrastructure/config/di/composition.py` (remove
    `create_repository_for_settings`).
  - `src/infrastructure/config/di/__init__.py` (remove the re-export
    entries).
  - `tests/unit/test_lifespan.py` (rewrite to use
    `container.repositories.kanban`).
  - `tests/unit/test_repository_selection.py` (rewrite to use
    `create_kanban_repository_for_settings`).
  - `tests/architecture/` (new test file).
- Affected configuration: none.
- No dependency changes.
- No HTTP / DB / domain / application behaviour changes.
- This change is independent of the other three skeleton/error/use-case
  changes and can land in any order, as long as
  `align-project-skeleton-to-hex-skill` has introduced the
  `hexagonal-architecture-conformance` capability first.
