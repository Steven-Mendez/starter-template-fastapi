## Why

`src/features/authorization/adapters/outbound/sqlmodel/repository.py` houses `SQLModelAuthorizationAdapter` and `SessionSQLModelAuthorizationAdapter` (classes named `*Adapter`) inside a file named `repository.py`. The rest of the outbound-adapter codebase consistently names files after their class suffix (`adapter.py` for `*Adapter`, `repository.py` for `*Repository`). The mismatch costs cross-feature readability, grep predictability, and Import Linter contract clarity.

## What Changes

- Rename `src/features/authorization/adapters/outbound/sqlmodel/repository.py` → `src/features/authorization/adapters/outbound/sqlmodel/adapter.py` via `git mv` (history preserved).
- Update every import that targets `features.authorization.adapters.outbound.sqlmodel.repository` to the new module path.
- No class renames, no behavior changes, no new ports.

**Capabilities — Modified**: `authorization`.

## Impact

- **Code paths renamed**:
  - `src/features/authorization/adapters/outbound/sqlmodel/repository.py` → `src/features/authorization/adapters/outbound/sqlmodel/adapter.py`
- **Code paths with import updates** (verified via `rg`):
  - `src/features/authorization/adapters/outbound/sqlmodel/__init__.py:3` — the only direct import of `.repository`. Every other consumer (composition container, every test) imports from the package via `__init__.py`, so the rename is transparent to them.
- **Behavior**: none.
- **Backwards compatibility**: External features only reach the adapter through `authorization.composition.container`, so the public seam is unaffected.

## Depends on

- None. This change lands first in the `authorization` cluster.

## Conflicts with

- `make-authz-grant-atomic` (edits the same file) — must rebase on top of this rename.
- `improve-db-performance` (infra-deploy cluster; edits the same file for `lookup_subjects` cap) — must rebase on top of this rename. Coordination owned by the infra-deploy cluster.
