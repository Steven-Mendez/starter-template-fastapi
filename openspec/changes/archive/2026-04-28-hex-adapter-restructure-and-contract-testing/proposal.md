## Why

Inbound and outbound adapters are currently distributed across multiple top-level areas with mixed naming conventions, and contract testing is not formalized per port. This increases cognitive load and makes architectural drift likely as the codebase grows.

## What Changes

- Define explicit adapter topology for inbound and outbound concerns.
- Establish naming and placement conventions for adapters, ports, mappers, and views.
- Introduce mandatory contract testing suites per core port.
- Add architecture constraints to enforce adapter placement and dependencies.
- **BREAKING**: module paths and imports will change due to adapter reorganization.

## Capabilities

### New Capabilities
- `adapter-topology-conventions`: Define required folder topology and naming rules for inbound/outbound adapters.
- `port-contract-testing`: Define mandatory contract test suites for port implementations.

### Modified Capabilities
- None.

## Impact

- Affected code: import paths, DI composition modules, adapter packages, and test structure.
- Affected tooling: import-linter contracts and CI checks.
- Team impact: clearer conventions and faster onboarding at the cost of one-time migration effort.
