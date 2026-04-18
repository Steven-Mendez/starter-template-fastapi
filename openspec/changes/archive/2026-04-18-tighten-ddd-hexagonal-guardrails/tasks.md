## 1. Architecture Import Governance

- [x] 1.1 Add architecture test helpers that parse imports for modules under `src/`.
- [x] 1.2 Define explicit allowlist/denylist dependency matrix for domain, application, api, and infrastructure layers.
- [x] 1.3 Add failing diagnostics that report violated rule, source module, and forbidden target import.
- [x] 1.4 Replace/extend existing boundary smoke tests to use the new governance assertions.

## 2. Hexagonal + CQRS Adapter Boundary Enforcement

- [x] 2.1 Add tests that verify API routes depend on command/query handler providers, not repository adapters.
- [x] 2.2 Add tests that verify read endpoints use query handlers and write endpoints use command handlers.
- [x] 2.3 Update architecture documentation snippets to reflect strict adapter delegation rules.

## 3. Persistence Session Boundary Hardening

- [x] 3.1 Add tests asserting SQLModel repository operations run in explicit operation-scoped sessions.
- [x] 3.2 Add tests asserting domain/application modules do not reference SQLModel/SQLAlchemy session or engine symbols.
- [x] 3.3 Add tests asserting repository lifecycle close/dispose is invoked via composition/lifespan wiring.
- [x] 3.4 Verify in-memory and SQLModel adapters preserve behavior parity for core command/query paths.

## 4. Validation and Rollout

- [x] 4.1 Run `pytest` (unit architecture + persistence-focused tests) and fix boundary violations.
- [x] 4.2 Run `ruff` and `mypy` to ensure no regressions in quality gates.
- [x] 4.3 Update change artifacts if implementation uncovers boundary edge cases or rule exceptions.
