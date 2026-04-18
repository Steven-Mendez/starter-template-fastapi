## Context

The current codebase already migrated to a clean DDD + hexagonal structure in `src/`, with ports in application, domain rules in domain services/specifications, and persistence in infrastructure adapters. However, boundary enforcement relies on lightweight string assertions, and persistence/session boundaries are implied rather than codified as explicit architecture contracts.

Recent guidance from Context7 for FastAPI and SQLModel reinforces two practices relevant here: (1) keep adapters thin and delegate through dependency-injected handlers/services, and (2) manage SQLModel sessions via scoped context boundaries with explicit startup/shutdown ownership for long-lived resources. This change formalizes those practices into testable specs and guardrails.

## Goals / Non-Goals

**Goals:**
- Make dependency-direction violations detectable via stronger architecture tests with actionable diagnostics.
- Enforce adapter boundary behavior: API routers delegate to command/query handlers only.
- Define explicit repository adapter session/transaction lifecycle expectations for SQLModel and in-memory parity.
- Keep changes incremental and compatible with existing API contracts and migration status.

**Non-Goals:**
- No rewrite of domain model or endpoint payload contracts.
- No introduction of distributed CQRS infrastructure (message buses, event sourcing, projections).
- No mandatory runtime framework swap or major dependency expansion.

## Decisions

### Decision 1: Introduce explicit import-governance capability
- **Choice**: Add a new capability (`architecture-import-governance`) focused on deterministic import-boundary enforcement.
- **Rationale**: Existing checks catch obvious drift but can miss transitive or subtle boundary leaks.
- **Alternatives considered**:
  - Keep string-based checks only: low effort, lower confidence.
  - Full external architecture platform: stronger, but unnecessary complexity for current project size.

### Decision 2: Split persistence boundary from generic dependency rule
- **Choice**: Add `persistence-session-boundary` as a standalone capability.
- **Rationale**: Session lifecycle and transaction semantics are critical and deserve independently testable requirements.
- **Alternatives considered**:
  - Fold into `sqlmodel-postgresql-persistence` only: simpler docs but weaker cross-adapter parity and less focused tests.

### Decision 3: Tighten existing capability requirements rather than introducing parallel specs
- **Choice**: Modify `architecture-dependency-rules`, `hexagonal-layer-boundaries`, `lightweight-cqrs`, and `sqlmodel-postgresql-persistence`.
- **Rationale**: These are authoritative capabilities already used by the project; updating them keeps a single source of truth.
- **Alternatives considered**:
  - Add only new specs: avoids edits but fragments architecture policy and increases ambiguity.

### Decision 4: Keep enforcement in unit/architecture tests integrated into CI
- **Choice**: Require boundary checks to run in standard test workflow (`pytest` unit lane).
- **Rationale**: Fast feedback and low operational overhead.
- **Alternatives considered**:
  - Separate CI job with custom tooling: may improve isolation but delays feedback and increases maintenance.

## Risks / Trade-offs

- **[Risk] Overly strict import rules create false positives** -> **Mitigation**: encode allowlist/denylist explicitly and document exceptions in tests/specs.
- **[Risk] Additional tests increase maintenance cost** -> **Mitigation**: keep policy focused on layer contracts, not file-level implementation details.
- **[Risk] Session boundary rules may diverge from adapter realities** -> **Mitigation**: include parity scenarios across in-memory and SQLModel adapters and validate through repository-level tests.

## Migration Plan

1. Add/modify spec files for architecture and persistence guardrails.
2. Implement or strengthen architecture tests to cover import governance and adapter delegation rules.
3. Add/adjust persistence adapter tests for session lifecycle and transaction boundary behavior.
4. Validate with `pytest`, `ruff`, and `mypy` in the existing quality gates.
5. Keep API behavior unchanged while improving enforcement internals.

Rollback strategy: if enforcement proves too strict, revert new boundary checks first while preserving production behavior.

## Open Questions

- Should import-governance be implemented using pure stdlib AST parsing or a lightweight dedicated analyzer dependency?
- Do we want a temporary exception mechanism for legacy modules outside `src/`, or keep scope strictly on `src/` only?
