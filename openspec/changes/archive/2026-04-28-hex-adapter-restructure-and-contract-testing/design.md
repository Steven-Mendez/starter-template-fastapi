## Context

The architecture is conceptually hexagonal, but adapter locations and naming are not fully explicit. Without strict topology and contract testing, boundaries can erode through accidental imports and mixed responsibilities. A structured reorganization plus enforceable tests will preserve architectural integrity as features expand.

## Goals / Non-Goals

**Goals:**
- Establish explicit inbound/outbound adapter package structure.
- Standardize naming conventions for ports, adapters, mappers, and read-model helpers.
- Add reusable contract test suites for each major port interface.
- Enforce architecture constraints in CI.

**Non-Goals:**
- Redesigning business workflows or domain aggregates.
- Replacing existing frameworks solely for stylistic consistency.
- Achieving zero-risk migration without temporary compatibility layers.

## Decisions

1. Adopt explicit topology convention for adapter placement.
   - Rationale: makes boundary intent obvious and discoverable.
   - Alternative: keep current layout and rely on documentation. Rejected due to drift risk.

2. Define strict naming rules (`*Port`, `*Adapter`, `*Mapper`, `*ReadModel`) and enforce via architecture tests where practical.
   - Rationale: reduces semantic ambiguity and improves searchability.

3. Build reusable contract test harnesses for repository and unit-of-work ports.
   - Rationale: each adapter implementation must prove compliance with same behavioral contract.

4. Migrate in phases with compatibility imports to minimize disruption.
   - Rationale: breaking path changes are expected but can be controlled with staged updates.

## Risks / Trade-offs

- [Risk] Large path migration creates noisy diffs and merge conflicts → Mitigation: execute in planned phases with freeze windows and automated import updates.
- [Risk] Contract tests become brittle if over-specified → Mitigation: specify externally observable behavior, not internal implementation details.
- [Risk] Team slows temporarily during convention adoption → Mitigation: publish concise migration guide and examples.
