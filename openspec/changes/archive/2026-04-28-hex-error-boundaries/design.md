## Context

The project already separates domain, application, API, and infrastructure layers, but technical exceptions from persistence can bypass an explicit application contract and surface as generic HTTP 500 responses. This weakens hexagonal boundaries because outbound concerns leak into inbound behavior. The system needs deterministic translation rules so each class of failure is represented once in application language and then mapped once to HTTP language.

## Goals / Non-Goals

**Goals:**
- Define a canonical application error taxonomy for business vs technical failures.
- Enforce adapter-to-application error translation at a single boundary.
- Define a deterministic HTTP mapping table from application errors to status and payload.
- Preserve domain purity by preventing HTTP/infrastructure types in domain and use-case cores.

**Non-Goals:**
- Rewriting domain invariants or changing core business rules.
- Introducing cross-service distributed tracing standards beyond local structured metadata.
- Full i18n error message localization.

## Decisions

1. Introduce explicit application error variants for technical failure classes.
   - Rationale: use cases and handlers can reason over stable semantic categories without depending on adapter exceptions.
   - Alternative considered: map adapter exceptions directly in API layer. Rejected because it leaks outbound details to inbound transport.

2. Require outbound adapters to raise typed infrastructure exceptions, then map them to application errors in application boundary handlers.
   - Rationale: preserves adapter specificity while keeping use-case contracts framework-agnostic.
   - Alternative considered: force adapters to emit application errors directly. Rejected because it couples infrastructure to application contracts.

3. Define canonical HTTP mapping matrix and payload fields (`code`, `message`, `details`, `trace_id`).
   - Rationale: deterministic contracts improve client behavior and incident triage.
   - Alternative considered: status-only mapping without stable codes. Rejected due to low machine readability.

4. Add compliance tests at three levels: adapter translation tests, use-case error propagation tests, and API contract tests.
   - Rationale: prevents regressions when adapters or handlers evolve.

## Risks / Trade-offs

- [Risk] Existing clients depend on legacy 500 patterns → Mitigation: document breaking matrix and provide migration notes with examples.
- [Risk] Error taxonomy may grow inconsistently over time → Mitigation: central registry and review checklist for new error codes.
- [Risk] Over-mapping can hide low-level diagnostics → Mitigation: preserve original exception context in structured logs only (not client payload).
