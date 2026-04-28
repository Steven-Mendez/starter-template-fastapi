## 1. Port redesign

- [x] 1.1 Define segregated command, query, and lookup port interfaces with explicit responsibilities.
- [x] 1.2 Remove projection-style methods from command ports and update use case dependencies.
- [x] 1.3 Update adapters to implement the new port boundaries.

## 2. Mapping boundary refactor

- [x] 2.1 Remove application DTO dependencies from persistence mappers.
- [x] 2.2 Introduce read-model mapping at application or inbound adapter boundary.
- [x] 2.3 Ensure query return types align with stable read-model contracts.

## 3. Verification

- [x] 3.1 Add architecture tests preventing infrastructure imports from application contracts.
- [x] 3.2 Add unit tests for command/query/lookup port conformance in use cases.
- [x] 3.3 Add integration tests validating unchanged functional behavior after interface split.
