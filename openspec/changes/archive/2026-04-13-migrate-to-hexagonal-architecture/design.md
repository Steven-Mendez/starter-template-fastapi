## Context

The current Kanban implementation works functionally but has architectural coupling that slows safe evolution:

- Route handlers call repository methods directly.
- Repository protocol and runtime backend selection are colocated.
- Feature modules import FastAPI and DI wiring concerns.
- Storage adapters and core rules are partially interleaved.

The migration must preserve HTTP behavior and test contracts while introducing clear hexagonal boundaries (`domain`, `application`, `infrastructure`) and a centralized composition root.

## Goals / Non-Goals

**Goals:**
- Enforce inward dependency direction from adapters to core.
- Introduce application use cases as the primary inbound port from HTTP adapters.
- Keep repository contracts as outbound ports and isolate concrete SQLModel adapters.
- Centralize runtime wiring and backend selection in one composition root.
- Preserve current API contract and existing repository behavior during migration.

**Non-Goals:**
- Redesigning the public API shape or endpoint URLs.
- Introducing CQRS/event sourcing in this migration.
- Replacing SQLModel/Alembic with another persistence stack.
- Rewriting all tests from scratch.

## Decisions

1. **Adopt a vertical hexagonal module layout for Kanban first**
   - Decision: Implement `kanban/domain`, `kanban/application`, `kanban/infrastructure`, and `kanban/api` boundaries incrementally.
   - Rationale: Limits blast radius while proving architecture with one bounded context.
   - Alternative considered: full project-wide folder move in one step; rejected due to high merge and regression risk.

2. **Introduce use-case services between routes and repository ports**
   - Decision: FastAPI routers depend on use-case handlers, not repositories.
   - Rationale: Keeps HTTP transport in adapters and business orchestration in application layer.
   - Alternative considered: retain direct repository access and only move files; rejected because it preserves current coupling.

3. **Move backend selection and adapter construction to composition root**
   - Decision: `dependencies`/wiring modules own settings-based adapter selection.
   - Rationale: Removes infrastructure decisions from repository port modules.
   - Alternative considered: keep factory in repository module with lazy imports; rejected because it violates dependency inversion intent.

4. **Preserve behavior with compatibility seams during migration**
   - Decision: Keep temporary aliases/shims where needed while tests are updated.
   - Rationale: Maintains test and runtime stability across phased refactors.
   - Alternative considered: remove compatibility paths immediately; rejected due to avoidable breakage.

## Risks / Trade-offs

- **[Risk] Import cycles during package split** -> **Mitigation:** move interfaces first, then adapters, and run import checks after each slice.
- **[Risk] Contract drift while introducing use cases** -> **Mitigation:** keep repository contract tests and API integration tests mandatory in each phase.
- **[Risk] Parallel work conflicts on shared wiring files** -> **Mitigation:** assign lane ownership and integrate frequently through a single orchestration pass.
- **[Risk] Temporary duplication between old and new paths** -> **Mitigation:** add explicit cleanup tasks with acceptance checks before archive.

## Migration Plan

1. Extract repository interfaces and domain rules into stable core modules.
2. Add application use-case handlers that mirror existing API operations.
3. Refactor routers to call use-case handlers while keeping response contracts unchanged.
4. Move adapter factories/backend selection into composition root wiring.
5. Relocate SQLModel/SQLite/PostgreSQL implementations under infrastructure adapters.
6. Update tests and add architecture boundary checks.
7. Remove temporary compatibility seams once parity is verified.

## Rollback Strategy

- Keep migration in small, reversible commits per lane.
- Preserve previous module entry points until final cleanup.
- If regressions appear, route dependencies can temporarily point back to legacy repository wiring while fixes are applied.

## Open Questions

- Should the first slice keep Pydantic models as application DTOs, or introduce separate domain DTOs immediately?
- Do we enforce boundaries only by convention first, or add automated import-lint rules in this same change?
- Should health readiness depend on a dedicated readiness port instead of repository lifecycle checks directly?
