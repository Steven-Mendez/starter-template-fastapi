## Context

The DI module declares two compatibility surfaces with no production
consumers:

- `ConfiguredAppContainer.repository` — a property aliasing
  `self.repositories.kanban`, documented as
  `"Backward-compatible alias to the kanban repository."`.
- `create_repository_for_settings(settings)` — a function delegating to
  `create_kanban_repository_for_settings(settings)`, documented as
  `"Backward-compatible helper for callers expecting a single repository."`.

`rg` confirms the only consumers are two unit tests:
`tests/unit/test_lifespan.py` and `tests/unit/test_repository_selection.py`.
No module under `src/` references either symbol. The starter template has
no prior version, so the "backward-compatible" justification does not
apply.

## Goals / Non-Goals

**Goals:**
- Remove both aliases.
- Rewrite the two consuming tests to use the canonical names.
- Add an architecture test that fails on future "backward-compatible"
  aliases without production consumers under
  `src/infrastructure/config/di/`.

**Non-Goals:**
- Renaming `create_kanban_repository_for_settings` or the
  `RuntimeRepositories` dataclass.
- Touching any other DI surface.
- Generalising the architecture test to the whole repository — the rule
  is scoped to the DI module where the violation actually occurred.

## Decisions

### D1 — Hard delete, no deprecation period

**Decision:** delete both symbols outright in the same commit that
rewrites the two consuming tests. Do not introduce a `DeprecationWarning`
or a transitional period.

**Rationale:**

- This is a starter template. There are no external consumers to warn.
- Both symbols already advertise themselves as compatibility shims; the
  cost of removal is one search-replace per test.
- A deprecation cycle would re-introduce the very pattern the change
  is removing.

**Alternatives considered:**

- Mark both symbols with `warnings.warn(DeprecationWarning, ...)` and
  remove in a future change. Rejected: no benefit; doubles the diff
  and the cognitive load.

### D2 — Architecture test scoped to the DI module

**Decision:** the new test
(`tests/architecture/test_di_no_unconsumed_compat_aliases.py`) walks
only `src.infrastructure.config.di` modules. It does not assert
across the whole repository.

**Rationale:**

- The pattern that motivated this change is local to the DI module.
- A repo-wide rule would risk false positives in legitimate
  compatibility scenarios (e.g. an explicit deprecation window for a
  public package surface, which a starter template does not have but a
  forked downstream might add).

**Alternatives considered:**

- Repo-wide rule. Rejected for the reason above. If the pattern ever
  resurfaces outside the DI module, extend the test rather than
  relying on a broad regex.

## Risks / Trade-offs

- **[Risk] A user of this template downstream may depend on
  `container.repository` or `create_repository_for_settings`.**
  → Mitigation: announce the removal in `README.md` (the change
  description / changelog area). The replacement names already exist
  in the public DI surface (`container.repositories.kanban`,
  `create_kanban_repository_for_settings`), so the migration is a
  one-line search-replace.

- **[Trade-off] The architecture test introduces a string check
  ("backward-compatible") on docstrings.**
  This is intentional: the rule targets the documentation contract, not
  identifier shape. If a future contributor genuinely needs a
  compatibility shim with production consumers, the test passes; if
  they leave the docstring without consumers, it fails with a clear
  message.

## Migration Plan

1. Run the audit (`rg "container\\.repository|create_repository_for_settings" -n src/ tests/`).
2. Delete the two symbols (sections 2 of `tasks.md`).
3. Rewrite the two tests (section 3 of `tasks.md`).
4. Add the architecture test (section 4 of `tasks.md`).
5. Run the full test matrix to verify no regression.

**Rollback:** revert the change PR. No data, schema, or HTTP contract
involvement.

## Open Questions

- None.
