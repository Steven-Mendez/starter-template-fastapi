## Why

Current repository ports mix command and query concerns and some infrastructure mappers depend on application-level DTO contracts. This reduces boundary clarity, weakens port cohesion, and makes future CQRS evolution and adapter substitution harder.

## What Changes

- Redefine ports with strict segregation: command mutation port, query projection port, and optional lookup port.
- Move cross-concern lookups out of command repository interfaces where possible.
- Define mapping boundaries so infrastructure does not depend on application transport contracts.
- Introduce explicit read-model contracts for query outputs.
- **BREAKING**: existing port interfaces and adapter implementations will change signatures and responsibilities.

## Capabilities

### New Capabilities
- `command-query-port-segregation`: Define normative separation and allowed responsibilities for command/query/lookup ports.
- `infrastructure-mapping-isolation`: Define mapping boundary rules preventing infrastructure dependence on application DTO contracts.

### Modified Capabilities
- None.

## Impact

- Affected code: application ports, use cases, repository adapters, and mapping modules.
- Affected tests: unit tests for use cases and integration tests tied to previous port contracts.
- Long-term effect: simpler adapter replacement and clearer path to dedicated read models.
