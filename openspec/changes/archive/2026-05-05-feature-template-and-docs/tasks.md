## 1. Template package skeleton

- [x] 1.1 Create `src/features/_template/__init__.py` and the subdirectory tree (`domain/`, `application/{ports/inbound,ports/outbound,commands,queries,contracts,errors,use_cases}/`, `adapters/{inbound/http,outbound/persistence}/`, `composition/`, `tests/{fakes,unit,integration,e2e}/`)
- [x] 1.2 Add `__init__.py` to every subdirectory
- [x] 1.3 Add a placeholder aggregate `domain/models/template_example.py` with a tiny `@dataclass` and `TODO(template):` markers
- [x] 1.4 Add a placeholder outbound port `application/ports/outbound/template_repository.py` with a `Protocol`
- [x] 1.5 Add a placeholder inbound Protocol `application/ports/inbound/template_example.py`
- [x] 1.6 Add a placeholder use case `application/use_cases/template_example.py` returning a static `Ok` so mypy/import-linter pass
- [x] 1.7 Add a placeholder router `adapters/inbound/http/router.py` (empty `APIRouter`) and a placeholder `composition/wiring.py` that intentionally is NOT registered in `src/main.py`
- [x] 1.8 Run `make check` and confirm no new errors mention `src/features/_template/`

## 2. Template README

- [x] 2.1 Write `src/features/_template/README.md` with the 11-step recipe described in the design
- [x] 2.2 Cross-link each step to the equivalent file in `src/features/kanban/`
- [x] 2.3 Include a "Tests" section detailing the order: domain → use cases → contracts → integration → e2e
- [x] 2.4 Include a "Wiring" section showing the `register_<feature>(app, platform)` boilerplate to add to `src/main.py`

## 3. hex-design-guide rewrite

- [x] 3.1 Replace all references to `src/{api,application,domain,infrastructure}` with `src/platform/` and `src/features/<F>/{...}` paths
- [x] 3.2 Add a section "Inbound port convention" describing the Protocol-per-use-case rule
- [x] 3.3 Add a section "Outbound port convention" describing port location and naming
- [x] 3.4 Add a section "Platform vs feature" listing what is allowed in `src/platform/`
- [x] 3.5 Add a section "Conformance contracts" listing each import-linter contract with rationale
- [x] 3.6 Add a section "Reading order" pointing to README → Kanban → `_template/` → tests
- [x] 3.7 Add a final "Migration from layer-first" subsection for old clones

## 4. Root README rewrite

- [x] 4.1 Update "Quick start" with `fastapi dev`, `make test`, `make ci`
- [x] 4.2 Replace "Project layout" tree with the feature-first layout
- [x] 4.3 Add "Add a new feature" section linking to `_template/README.md`
- [x] 4.4 Update "Conformance" section to reference the new contracts
- [x] 4.5 Update "OpenSpec" section to list active and archived changes accurately
- [x] 4.6 Add "Migration from layer-first" subsection with a path-rename table

## 5. Smoke validation

- [x] 5.1 In a throwaway branch, follow the `_template/` README to add a `pingpong` feature exposing `GET /api/pingpong/{n}` returning `{"pong": n}`
- [x] 5.2 Verify `make check && make test` pass
- [x] 5.3 Discard the throwaway branch (do not merge)
- [x] 5.4 Note any friction in `_template/README.md` discovered during the smoke check and refine the docs

## 6. Verification

- [x] 6.1 `make check` green
- [x] 6.2 `pytest --collect-only` produces zero errors mentioning `_template`
- [x] 6.3 OpenAPI document contains zero paths derived from `_template`
- [x] 6.4 `rg "TODO\(template\):" src/features/_template` returns one or more matches in every placeholder file
- [x] 6.5 README "Quick start" commands executed in a clean clone produce a running API and a passing `/health`
