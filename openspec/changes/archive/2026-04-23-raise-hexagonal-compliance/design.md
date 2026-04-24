## Context

The project already enforces inward dependencies and uses command/query separation, but it still leaks domain-level contracts into the API adapter surface and keeps some child-entity persistence operations in repository adapters. For a starter template, this creates ambiguity: teams can copy patterns that are "close" to hexagonal but not strict enough for long-term boundary safety.

The goal of this change is to make the template a stronger reference baseline by tightening contract ownership and enforcing hard architectural boundaries in CI without introducing heavyweight distributed architecture patterns.

## Goals / Non-Goals

**Goals:**
- Make API adapters transport-only and application-contract-only for orchestration and error/result handling.
- Keep driven repository contracts aggregate-oriented and free of child-entity CRUD orchestration APIs.
- Strengthen architecture tests with explicit, actionable failures for direct and transitive leaks.
- Keep enforcement focused on concrete boundary rules (imports/layering/dependency direction).

**Non-Goals:**
- Introduce full tactical DDD patterns (domain events, aggregate factories, rich value-object model) beyond what is necessary for hexagonal boundaries.
- Introduce distributed CQRS/event-sourcing infrastructure.
- Redesign external API behavior or break existing endpoint semantics.

## Decisions

### 1) API adapter contracts are application-owned, not domain-owned
- Decision: route handlers and API mappers will consume and produce application-facing contracts; direct imports of domain `Result`, domain errors, or domain entities in API modules become violations.
- Rationale: this preserves the primary adapter role (transport translation) and reduces coupling between HTTP concerns and domain internals.
- Alternative considered: allow domain `Result` types in API "for simplicity." Rejected because it leaks core internals into transport and weakens boundary clarity.

### 2) Repository contract remains one per aggregate root
- Decision: persistence ports for Kanban remain aggregate-oriented (`Board` as aggregate root) and prohibit child-entity orchestration methods as first-class repository APIs.
- Rationale: keeps invariants and orchestration outside driven adapters and aligns with "one repository per aggregate" guidance already present in project specs.
- Alternative considered: keep helper child-entity operations for convenience. Rejected because it invites orchestration drift into infrastructure.

### 3) Governance is enforced through architecture and lint checks
- Decision: enforce boundaries with import/layering checks in tests plus existing lint/typecheck gates, without introducing a synthetic aggregate "score" test.
- Rationale: concrete pass/fail boundary rules are easier to reason about and maintain in a starter template.
- Alternative considered: weighted compliance score gate. Rejected because the metric can become subjective and disconnected from real boundary violations.

### 4) Keep CQRS lightweight and in-process
- Decision: maintain split command/query handlers but tighten contract boundaries so CQRS remains structural and transport-agnostic.
- Rationale: this improves hexagonal quality without introducing unnecessary complexity.
- Alternative considered: expand to async buses/projections. Rejected as out of scope for starter template.

## Risks / Trade-offs

- **[Risk] Contract churn across API and application layers** -> **Mitigation:** introduce transitional mappers and focused tests to preserve endpoint behavior while changing internals.
- **[Risk] Over-constraining contributors with strict import policies** -> **Mitigation:** provide clear diagnostics and architecture docs so violations are easy to fix.
- **[Trade-off] Additional abstraction in application contracts** -> **Mitigation:** keep contracts minimal and scoped to use cases; avoid introducing unnecessary DTO hierarchies.

## Migration Plan

1. Define/adjust capability specs for adapter purity, contract ownership, and import/dependency governance.
2. Refactor application contracts and API mappings to remove direct domain contract leakage.
3. Refactor repository interfaces/adapters toward aggregate-only persistence surface.
4. Extend architecture tests and CI checks for dependency direction/import governance.
5. Validate existing endpoint behavior with unit/integration/e2e suites.

Rollback strategy: if strict rules cause unexpected breakages, keep diagnostics visible but temporarily scope enforcement to the failing rule set while preserving architectural test output for remediation.

## Open Questions

- Do we treat any API import of domain contracts as hard-fail, or allow narrowly scoped exceptions for read-only projections?
