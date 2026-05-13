## Context

The `authorization` feature's outbound SQLModel module breaks the codebase-wide naming convention: classes suffixed `*Adapter` live in `repository.py`. Every other outbound adapter directory (`authentication`, `users`, `outbox`, `email`, `file_storage`) names its file after the class suffix. The fix is a pure rename; no behavior or contract changes.

## Decisions

### Decision 1: Direction — `Repository → Adapter` (file renamed to `adapter.py`)

- **Chosen**: rename the **file** to match the **class** (`adapter.py` for `*Adapter`). The classes are already named `SQLModelAuthorizationAdapter` and `SessionSQLModelAuthorizationAdapter`, and other outbound directories already follow the `adapter.py` convention (e.g. `src/features/email/adapters/outbound/console/adapter.py`, `src/features/email/adapters/outbound/smtp/adapter.py`, `src/features/file_storage/adapters/outbound/s3/adapter.py`).
- **Rejected**: renaming the classes to `*Repository` and keeping the file as `repository.py`. That would force a far larger blast radius (every test, every composition wiring, the `AuthorizationPort` docstrings) and would conflict with the established sibling convention. The file rename is the smaller, safer move.

### Decision 2: Use `git mv` to preserve history

- **Chosen**: a single `git mv` so `git log --follow` keeps working and PR review tooling shows the rename as a rename (no apparent deletion + creation).
- **Rejected**: `cp` + `rm`. Loses the rename hint and pollutes the diff.

### Decision 3: No class renames in this change

- The `Session*Adapter` companion stays. There is no `*Adapter` → `*Repository` flip here. If the codebase later decides to standardize on the other direction, that is a separate proposal.

## Risks / Trade-offs

- **Risk**: import-update misses. Mitigation: `make lint`, `make typecheck`, and `make ci` will all fail loudly on a missed import.
- **Risk**: collision with concurrent edits on the same file from `make-authz-grant-atomic` and `improve-db-performance`. Mitigation: this change lands **first** in the authorization cluster; the two follow-ons rebase on top.

## Migration Plan

Single PR. No DB migrations. Rollback = revert.

1. `git mv` the file.
2. Run `make lint` and rip out any stale imports.
3. Run `make ci`.

## Depends on

- None.

## Conflicts with

- `make-authz-grant-atomic`: same file edited. This rename lands first; `make-authz-grant-atomic` rebases.
- `improve-db-performance` (infra-deploy cluster): same file edited for `lookup_subjects` cap. This rename lands first; that change rebases.
