## Context

The repository's intent is "starter template": humans clone it and add features. The two prior changes establish the feature-first layout (Kanban as the example) and the test conventions (co-located, contract suites, fakes). This change closes the loop by giving newcomers a guided path: a `_template/` scaffold to copy and updated written guidance that matches reality. Without it, the only way to learn the conventions is to read Kanban end-to-end and infer rules.

## Goals / Non-Goals

**Goals:**

- Reduce "time to first feature" to under 30 minutes for someone who has read the README.
- Keep the architecture documentation in sync with the actual layout.
- Make it impossible to drift between Kanban (example) and `_template/` (scaffold): both share the same file structure, with `_template/` containing inert placeholders.

**Non-Goals:**

- Generating features automatically via a CLI (e.g., a `cookiecutter`-style command). The user copies and renames manually; the README is explicit enough.
- Documenting every Pydantic/SQLModel/FastAPI feature; this is a hexagonal template, not a framework tutorial.
- Translating documentation to other languages.

## Decisions

### D1. `_template/` is a real Python package, not a docs-only artifact

It contains `__init__.py`, `domain/`, `application/{ports/inbound,ports/outbound,commands,queries,contracts,errors,use_cases}/`, `adapters/{inbound/http,outbound/persistence}/`, `composition/`, and a `tests/` stub. Files contain `Protocol` placeholders, an example use case `template_example_use_case.py`, and `pass` stubs. mypy must pass; import-linter must pass; pytest must collect zero tests but no errors.

**Alternatives considered:**

- *Markdown-only template*: rejected — copy-paste correctness is fragile when docs and code drift; a real package guarantees the structure.
- *Cookiecutter*: rejected — adds tooling and indirection for what is a one-time copy.

### D2. `_template/` is not registered in `src/main.py`

There is no `register_template` call. The README explicitly tells new authors to add the call after they rename the folder.

### D3. `_template/README.md` is the authoritative recipe

It walks through:

1. `cp -r src/features/_template src/features/<your_feature>` and rename the package.
2. Define the aggregate root in `domain/`.
3. Declare outbound ports (repository, UoW if needed) in `application/ports/outbound/`.
4. Declare inbound port Protocols, one per use case.
5. Write commands/queries/contracts/errors.
6. Write use cases that depend on ports only.
7. Implement outbound adapters (persistence, query) and inbound adapter (HTTP routers, schemas, mappers).
8. Wire `composition/wiring.py` and add `register_<feature>(app, platform)` to `src/main.py`.
9. Write tests in the same order as you wrote the code: domain → use cases (with fakes) → contracts → integration → e2e.
10. Run `make check && make test`.

It explicitly references Kanban for each step ("see `src/features/kanban/...` for a worked example").

### D4. Single architecture doc

The existing `hex-design-guide.md` is rewritten in place; sections referencing the old layout are replaced. A short "Reading order" header points to: this guide → Kanban → `_template/` → tests.

### D5. Root `README.md` rewrite minimal but accurate

Sections updated:

- Quick start (paths/commands).
- Project layout (tree of `src/platform/` + `src/features/kanban/` + `src/features/_template/`).
- Add a new feature (link to `_template/README.md`).
- Conformance (commands + contracts).
- OpenSpec (kept; updated to match current archived/active changes).
- Migration from layer-first (one short paragraph for old clones).

## Risks / Trade-offs

- **[Risk] `_template/` rots over time** → Mitigation: it's part of the test suite (collects zero tests but its imports are exercised by `pytest --collect-only`); import-linter contracts apply to it; CI catches drift.
- **[Risk] Two sources of truth (Kanban vs `_template/`)** → Mitigation: `_template/` is intentionally minimal — it contains structure, not behavior. The README repeatedly defers to Kanban for "real" examples.
- **[Trade-off] Docs in two files** → Accepted: README is the entry point, `hex-design-guide.md` is the deep dive. Cross-link both ways.

## Migration Plan

1. Create `src/features/_template/` with the package skeleton and placeholder modules.
2. Write `src/features/_template/README.md` with the 10-step recipe.
3. Add `__init__.py` files so the package imports cleanly; ensure mypy and import-linter pass.
4. Rewrite `hex-design-guide.md` against the new layout.
5. Rewrite the affected sections of root `README.md`.
6. Smoke-check by following the recipe end-to-end against a throwaway feature `pingpong` that exposes a single `GET /api/pingpong/{n}` and proves the recipe is complete; then delete the throwaway.

Rollback: revert the merge commit; only additive changes outside the runtime path.

## Open Questions

- Should `_template/` ship a CONTRIBUTING.md alias? (Lean: no — the root README already points to OpenSpec/SDD skills.)
- Do we lint `_template/` for "TODO:" markers? (Lean: yes — every placeholder is a `TODO(template):` line so future authors find them with grep.)
