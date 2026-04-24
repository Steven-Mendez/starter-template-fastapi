## 1. API/Application Contract Boundary Hardening

- [x] 1.1 Define application-owned result/error contracts for command/query handlers so API adapters do not import domain shared result/error modules.
- [x] 1.2 Refactor `src/api/*` handlers and mappers to consume only application contracts plus transport schemas.
- [x] 1.3 Update boundary tests to assert API modules do not import domain model/error/result contracts directly.

## 2. Aggregate-Oriented Repository Surface

- [x] 2.1 Refactor Kanban driven repository ports to expose aggregate-oriented operations only (load/save/delete/find aggregate context) and remove child-entity orchestration APIs from the contract.
- [x] 2.2 Update persistence adapters (`in_memory` and `sqlmodel`) to implement the new aggregate-oriented contract while keeping business sequencing decisions outside adapters.
- [x] 2.3 Refactor command/query handlers and test builders to work with the aggregate-oriented contract.

## 3. Import Governance and Architecture Rules

- [x] 3.1 Extend architecture dependency matrix and diagnostics to fail API-to-domain contract leakage with actionable error messages.
- [x] 3.2 Add/adjust architecture unit tests for direct and transitive governance checks in zero-exception mode.
- [x] 3.3 Update architecture documentation to reflect stricter inbound adapter and repository boundary rules.
