## Why

The current codebase is close to strict hexagonal architecture, but it still permits boundary leakage through transitive imports and runtime wiring heuristics (`_engine` inspection). We need a zero-tolerance architecture mode with explicit composition contracts and strict FastAPI adapter rules so drift is blocked by design and CI.

## What Changes

- Move runtime wiring modules under `src/` layer-owned packages and prohibit `src/*` runtime coupling to root-level helper modules.
- Consolidate composition-root ownership so container initialization/teardown happens only in app lifespan, with fail-fast behavior when lifecycle state is missing.
- Replace repository implementation introspection (private attribute checks) with explicit, typed Unit of Work factory wiring from composition root.
- Enforce strict FastAPI adapter contracts: `Annotated` dependency aliases, explicit response models for adapter responses, and no domain sentinels leaked into HTTP transport logic.
- Strengthen architecture tests to detect direct and transitive dependency violations across the full import graph reachable from `src/`, with no temporary exceptions.
- Tighten observability and error contracts so unhandled exceptions always emit structured correlated logs while preserving RFC 9457 Problem Details responses.

## Capabilities

### New Capabilities
- `architecture-import-governance`: enforce strict direct + transitive import governance with zero-exception CI enforcement.

### Modified Capabilities
- `composition-root-wiring`: enforce lifecycle-owned container wiring and explicit Unit of Work factory composition.
- `hexagonal-layer-boundaries`: disallow transitive API adapter coupling to infrastructure through shared dependency modules.
- `architecture-dependency-rules`: expand boundary checks to include non-`src/` modules imported by `src/` and report transitive violations.
- `application-mapping-boundary`: formalize typed FastAPI dependency aliases and explicit handler dependency contracts at adapter edge.
- `lightweight-cqrs`: enforce strict read/write handler dependency contracts per endpoint category.
- `api-core`: require `/health` response contract fields for persistence backend/readiness as part of stable API surface.
- `api-observability-baseline`: require structured logging for unhandled exceptions with request correlation context.
- `request-correlation-logging`: require deterministic request ID propagation into response headers and error telemetry.
- `rfc9457`: preserve strict Problem Details payload/media type semantics while adding correlation-safe extensions.

## Impact

- Affected code: runtime wiring modules (`dependencies.py`, `settings.py`, `problem_details.py`, `main.py`), `src/api/*`, `src/infrastructure/config/di/*`, architecture tests under `tests/unit/`, and observability/error handlers.
- Affected API surface: no endpoint path changes; `/health` and error responses remain compatible but become explicitly modeled and validated.
- Affected quality gates: stricter `pytest` architecture checks (direct + transitive), plus lint/type-checking for typed FastAPI dependency contracts.
