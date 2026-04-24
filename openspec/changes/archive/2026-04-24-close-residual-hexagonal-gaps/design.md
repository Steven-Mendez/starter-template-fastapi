## Context

Recent changes eliminated major API-to-domain leaks and moved command-side orchestration toward aggregate persistence. A follow-up audit still finds residual seams where boundaries are not yet self-enforcing:

1. Inbound adapters are coupled to concrete handler classes (`KanbanCommandHandlers`, `KanbanQueryHandlers`) rather than stable driver-port interfaces.
2. API schema modules import `src.application.contracts` enum types, which blurs transport ownership.
3. Concrete persistence adapters retain public child-entity helper methods not declared on repository ports.
4. Tests and builders still use those helper methods, preserving non-aggregate usage patterns.
5. API dependency modules expose repository accessors that can bypass CQRS handler boundaries.
6. API dependency modules construct concrete command handlers directly, and some routes inject the app container object instead of dedicated dependencies.

## Goals / Non-Goals

**Goals**
- Make inbound adapter dependencies interface-first (driver ports), not concrete-class-first.
- Keep API transport schemas fully transport-owned and mapper-translated.
- Ensure driven adapter public APIs match declared aggregate repository ports.
- Align tests with aggregate-oriented flows so test suites stop depending on non-port methods.
- Harden architecture checks so these rules remain enforced in CI.

**Non-Goals**
- Redesign endpoint payloads or business behavior.
- Introduce distributed CQRS/event-driven infrastructure.
- Perform broad DDD model redesign beyond boundary hardening.

## Decisions

### 1) Define explicit driver ports for command/query entry points
- **Decision:** Add application-layer `Protocol` contracts for command and query handler entry points, and type API dependency aliases/routes to those protocols.
- **Rationale:** Driver adapters should depend on stable ports, not concrete implementations.
- **Alternative considered:** Keep concrete handler type hints because they are "typed enough". Rejected because this still couples adapters to implementation classes.

### 2) Keep transport schemas adapter-owned
- **Decision:** API schema modules own wire enums/value literals; API mappers translate to/from application contract types.
- **Rationale:** Transport contracts must be versionable independently from application internals.
- **Alternative considered:** Reuse application enums directly in Pydantic models. Rejected because it weakens adapter boundary ownership.

### 3) Enforce driven adapter surface parity with ports
- **Decision:** Public adapter methods in production repository classes must be declared by the driven repository port; extra child-entity helpers are removed or made internal/non-production.
- **Rationale:** Public method drift creates hidden alternate orchestration paths and undermines aggregate boundaries.
- **Alternative considered:** Keep helper methods as convenience APIs. Rejected because tests already rely on them, making the drift structural.

### 4) Realign tests to hexagonal boundaries
- **Decision:** Builders and repository tests prepare state through aggregate-oriented port operations or command handlers; no test dependency on adapter-only child-entity methods.
- **Rationale:** Tests shape architecture over time; they must reinforce intended boundaries.
- **Alternative considered:** Keep current tests and rely only on production code discipline. Rejected because this allows boundary regressions to pass.

### 5) Block repository bypass at API dependency layer
- **Decision:** Remove API-level repository dependency providers intended for route use; keep only command/query handler dependencies and lifecycle-safe container access.
- **Rationale:** Prevents accidental direct persistence injection in inbound adapters.
- **Alternative considered:** Keep repository provider but document "do not use in routes". Rejected because unenforced guidance drifts.

### 6) Keep API dependency modules implementation-agnostic
- **Decision:** Composition root owns concrete command-handler construction via a command-handler factory exposed on the container; API dependency modules consume only ports/factories.
- **Rationale:** Prevents inbound adapters from importing concrete application handlers and strengthens swapability.
- **Alternative considered:** Keep handler construction in API dependencies. Rejected because adapter code becomes implementation-coupled.

### 7) Routes consume focused dependencies, not container objects
- **Decision:** Route signatures use dedicated handler/settings dependencies and SHALL NOT inject the full app container.
- **Rationale:** Limits route coupling surface and closes indirect access to unrelated resources.
- **Alternative considered:** Allow container injection for convenience in utility routes. Rejected because it weakens boundary discipline and reviewability.

## Risks / Trade-offs

- **Risk:** Test refactor may initially increase setup verbosity.
  - **Mitigation:** provide shared harness helpers centered on command/query flows.
- **Risk:** Protocol-first typing introduces additional interfaces.
  - **Mitigation:** keep ports minimal and aligned to existing handler methods.
- **Trade-off:** stricter adapter surface rules reduce convenience APIs.
  - **Mitigation:** keep helper logic in test utilities, not in production adapter contracts.

## Migration Plan

1. Add driver-port protocols and switch API dependency typing to those ports.
2. Introduce transport-owned wire enum types and mapper conversions.
3. Remove extra public adapter methods outside repository ports.
4. Refactor test builders/contracts to aggregate-oriented setup paths.
5. Extend architecture tests to enforce the new boundaries.
6. Update architecture docs and run full unit/integration validation.

## Open Questions

- Should we expose one coarse-grained command/query port per bounded context, or one port per use case, in this starter template baseline?
