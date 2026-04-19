## 1. Composition Root and Runtime Wiring

- [x] 1.1 Refactor container composition so repository and Unit of Work factory are selected in one place from settings.
- [x] 1.2 Update dependency providers to consume pre-wired container contracts and remove lazy container construction paths.
- [x] 1.3 Remove repository private-attribute strategy checks (for example `_engine`) from runtime wiring.
- [x] 1.4 Verify app lifespan remains the single owner of container/resource initialization and shutdown.

## 2. FastAPI Adapter Contract Alignment

- [x] 2.1 Introduce reusable `Annotated` dependency aliases for command/query handlers at API adapter boundary.
- [x] 2.2 Update router functions to use alias-based dependency signatures consistently.
- [x] 2.3 Add explicit `/health` response schema and enforce it via `response_model` (or typed return contract equivalent).

## 3. Hexagonal Boundary Enforcement Hardening

- [x] 3.1 Extend architecture dependency tests to analyze modules under `src/` plus root-level modules imported by them.
- [x] 3.2 Add transitive dependency path checks that fail when API modules reach infrastructure through intermediate modules.
- [x] 3.3 Ensure boundary failure diagnostics include violated rule, source module, and disallowed target/path.

## 4. Observability and Error Telemetry

- [x] 4.1 Add structured logging for unhandled exceptions with request correlation fields before returning Problem Details.
- [x] 4.2 Add/adjust tests to verify structured error log emission and RFC 9457 response behavior remain intact.

## 5. Validation, Documentation, and Rollout

- [x] 5.1 Update architecture/dependency documentation to describe explicit composition-root + UoW factory contracts.
- [x] 5.2 Run `uv run pytest` and resolve regressions in unit/integration/e2e checks.
- [x] 5.3 Run `uv run ruff check .` and `uv run mypy` to confirm style/type compliance.
