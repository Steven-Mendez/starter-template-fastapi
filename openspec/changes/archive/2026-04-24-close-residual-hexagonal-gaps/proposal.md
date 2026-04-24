## Why

The project is now mostly aligned with hexagonal architecture, but a deeper audit still shows boundary gaps that can let adapter coupling creep back in:

- Inbound API dependencies and routes are typed to concrete handler classes instead of explicit driver-port interfaces.
- Transport schemas still import application contract enums, so wire models are not fully adapter-owned.
- Persistence adapters expose public child-entity helper methods that are not part of the driven repository port.
- Test builders and repository contract tests still depend on those adapter-only helper methods, reinforcing non-aggregate workflows.
- API dependency modules still export repository accessors that can bypass command/query orchestration.
- API dependency modules instantiate concrete handler classes directly, coupling the inbound adapter to implementation details.
- Some routes (for example health) inject the full app container object instead of dedicated handler/settings dependencies.

These gaps do not break runtime behavior today, but they weaken long-term hexagonal guarantees and make architectural drift easier.

## What Changes

- Introduce explicit application driver-port protocols for command/query handler entry points, and make API dependencies/routes consume those ports.
- Move wire-specific schema types (such as card priority enums) fully into API schema modules, with mapper-level conversion to application contracts.
- Tighten driven adapter surfaces so public production methods match the declared repository port contract.
- Refactor tests/builders to use aggregate-oriented repository operations or application handlers instead of adapter-only child-entity shortcuts.
- Extend architecture tests to detect repository bypasses in API dependencies, schema-layer contract leakage, and adapter surface drift.
- Move command-handler construction into composition-root container factories and keep API dependencies interface-only.
- Replace route-level container injection with explicit handler/settings dependencies and enforce this in architecture tests.

## Capabilities

### New Capabilities
- None.

### Modified Capabilities
- `hexagonal-layer-boundaries`: enforce driver-port typing at inbound adapter boundaries and remove repository bypass vectors from API dependencies.
- `application-mapping-boundary`: keep transport schema modules adapter-owned and mapper-driven for enum/value translation.
- `lightweight-cqrs`: formalize command/query driver ports as the inbound contract for adapters.
- `repository-aggregate-compliance`: enforce adapter public-surface parity with aggregate repository ports and remove child-entity shortcuts.
- `architecture-dependency-rules`: require architecture tests for method-surface and dependency-provider boundary drift.
- `composition-root-wiring`: restrict API-facing container contracts to handler ports and lifecycle-safe resources.

## Impact

- Affected code: `src/api/*`, `src/application/*`, `src/infrastructure/persistence/*`, DI wiring modules, and architecture/contract tests under `tests/*`.
- Expected outcome: stricter and test-enforced hexagonal boundaries, especially around inbound ports and driven adapter APIs.
- Compatibility: no intended HTTP contract changes; focus is internal boundary hardening and test realignment.
