## Context

The project already enforces most DDD + hexagonal boundaries and ships with a FastAPI lifespan, CQRS handlers, and architecture tests. For strict mode, remaining drift is no longer acceptable:

1. API modules import a shared `dependencies.py` module that, in turn, imports infrastructure wiring, creating a transitive API -> infrastructure coupling path.
2. Unit of Work selection is resolved at runtime through repository internals (`hasattr(repo, "_engine")`), which is brittle and bypasses explicit composition-root contracts.
3. Runtime modules at repo root (`dependencies.py`, `settings.py`, `problem_details.py`) weaken machine-enforced layer policy because they sit outside the layer tree.

In parallel, FastAPI adapter conventions are not fully codified: dependency aliases are repeated inline, `/health` returns an untyped dictionary, and strict adapter contracts are not fully test-governed. These are not breaking today, but strict mode requires all of them to be explicit and enforced.

## Goals / Non-Goals

**Goals:**
- Ensure composition root is the single owner of runtime wiring decisions (container lifecycle + UoW factory).
- Remove transitive API -> infrastructure dependency leakage.
- Eliminate root-level runtime wiring ambiguity by governing root modules in architecture tests and moving wiring responsibilities into layer-owned modules.
- Standardize API adapter dependency declarations through typed aliases and explicit response contracts.
- Enforce zero-exception architecture checks (no temporary allowlist bypasses for forbidden imports).
- Improve architecture test fidelity to catch both direct and transitive boundary violations.
- Keep RFC 9457 behavior while improving operational observability for unexpected failures.

**Non-Goals:**
- No endpoint path or payload redesign outside explicit `/health` response modeling.
- No domain model rewrite or aggregate boundary redesign.
- No migration to distributed CQRS/event-driven infrastructure.
- No new persistence backend support in this change.

## Decisions

### Decision 1: Move runtime wiring authority fully into composition root
- **Choice**: Keep app startup/shutdown responsible for container creation and disposal, and make request dependencies fail fast if container state is missing instead of rebuilding it lazily.
- **Rationale**: Lifespan-scoped ownership is the recommended FastAPI pattern and avoids hidden side effects during request handling.
- **Alternatives considered**:
  - Keep lazy fallback (`get_app_container` creates container when absent): simpler, but hides initialization bugs and reintroduces adapter-selection logic in request code.
  - Build a global singleton container at import time: easy access, but weak test isolation and poor lifecycle control.

### Decision 2: Replace implementation introspection with explicit `uow_factory`
- **Choice**: Add an explicit Unit of Work factory to composition output (`AppContainer` or equivalent) and resolve command handlers from that factory, not via repository private attributes.
- **Rationale**: Makes backend-specific transaction strategy explicit, type-checkable, and architecture-safe.
- **Alternatives considered**:
  - Continue `_engine` checks on repository objects: fast but brittle and implicit.
  - Push UoW construction into each route: explicit but duplicates wiring and pollutes adapters.

### Decision 3: Govern runtime modules as architecture-scoped modules
- **Choice**: Include root-level runtime modules in architecture governance (and incrementally move them under `src/`), so they follow the same dependency matrix as layer modules.
- **Rationale**: Strict hexagonal policy cannot be reliably enforced if key runtime wiring modules live outside governed boundaries.
- **Alternatives considered**:
  - Keep root modules permanently out of scope: lower effort, but leaves a permanent policy blind spot.
  - Introduce broad exceptions for root modules: avoids short-term churn but undermines strict-mode guarantees.

### Decision 4: Codify FastAPI adapter contracts (dependency aliases + response model)
- **Choice**: Introduce `Annotated` dependency aliases for command/query handler dependencies, require explicit response models for adapter outputs (starting with `/health`), and keep domain sentinel mechanics out of HTTP transport code.
- **Rationale**: Reduces repeated signatures, improves editor/type support, and makes OpenAPI output and adapter boundaries stable.
- **Alternatives considered**:
  - Keep inline dependency declarations everywhere: functional but repetitive and error-prone.
  - Keep untyped `dict` responses: flexible but weaker contract guarantees.

### Decision 5: Strengthen architecture checks to include transitive module graph edges
- **Choice**: Expand architecture tests to evaluate direct and transitive imports for `src/` modules and governed root runtime modules, and fail on any API -> infrastructure path.
- **Rationale**: Current direct-import checks are necessary but insufficient for strict hexagonal governance.
- **Alternatives considered**:
  - Limit checks to `src/` files only: lower effort, misses known leak path.
  - Maintain transitive checks with temporary ignore-list: easier migration, weaker strictness.

### Decision 6: Preserve Problem Details contract while improving failure telemetry
- **Choice**: Keep RFC 9457 response behavior unchanged and add structured error logs in global unhandled-exception flow with request correlation fields.
- **Rationale**: Maintains API compatibility while improving incident diagnostics.
- **Alternatives considered**:
  - Add verbose error details in responses: better debugging but unsafe for production.
  - Leave telemetry unchanged: lower effort, weaker operational insight.

## Risks / Trade-offs

- **[Risk] Tightened architecture checks produce false positives** -> **Mitigation**: scope graph checks to Python modules reachable from `src/` and provide explicit violation diagnostics.
- **[Risk] Fail-fast container access may break tests that bypass lifespan** -> **Mitigation**: update test fixtures to initialize app/container through official startup paths.
- **[Risk] UoW factory contract introduces extra wiring complexity** -> **Mitigation**: keep factory signature minimal and colocated with existing composition code.
- **[Risk] Strict no-exception policy may temporarily block parallel feature work** -> **Mitigation**: stage refactor sequence so wiring cleanup and architecture checks land together in one bounded change.
- **[Risk] `/health` response modeling could unintentionally narrow payload flexibility** -> **Mitigation**: model current payload shape exactly and preserve existing fields.

## Migration Plan

1. Refactor runtime wiring modules into governed layer modules and update imports.
2. Update composition and dependency wiring contracts (container lifecycle ownership + explicit `uow_factory`).
3. Introduce strict API adapter contracts (`Annotated` aliases + response model coverage for `/health` and related adapter outputs).
4. Extend architecture tests for transitive checks, root-module governance, and zero-exception enforcement.
5. Add/adjust observability tests for unhandled exception structured logging and request correlation.
6. Run full quality gates (`pytest`, `ruff`, `mypy`) and fix regressions.

Rollback strategy: revert dependency/composition changes first (restore previous wiring) while retaining non-breaking test improvements for diagnostics.

## Open Questions

- None. This change intentionally chooses strict defaults: root runtime modules are governed, and architecture checks run in zero-exception mode.
