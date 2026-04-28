# health-readiness-contract Specification

## Purpose
Define a stable readiness contract where the health API reports persistence status without hardcoded infrastructure labels in the router, and backend naming is sourced from composition-time configuration.

## Requirements

### Requirement: HRC-01 - Health router must not hardcode persistence backend labels

**Priority**: High

The health route adapter MUST derive the persistence backend label from a composition/configuration boundary and MUST NOT embed concrete backend literals in route logic.

**Acceptance Criteria**:
1. The `/health` route has no hardcoded backend label literal (for example, no fixed `"postgresql"` value in router response construction).
2. The backend label exposed at `persistence.backend` is sourced from application settings provided through dependency wiring.
3. Changing the configured backend label changes the emitted `persistence.backend` value without modifying route code.

#### Scenario: Configured backend label is emitted

- Given: application settings configure `health_persistence_backend` as `"primary-db"`
- When: a client calls `GET /health`
- Then: the response contains `persistence.backend` equal to `"primary-db"`

#### Scenario: Router remains infrastructure-agnostic

- Given: the health route module is reviewed
- When: response payload creation is inspected
- Then: no concrete infrastructure backend string is embedded in route logic
- And: backend naming is obtained from the composition/configuration boundary

### Requirement: HRC-02 - Health readiness response shape remains stable while backend typing is implementation-agnostic

**Priority**: High

The health API contract MUST preserve existing response structure while allowing backend labels beyond a single concrete technology literal.

**Acceptance Criteria**:
1. `GET /health` response shape remains `{ status, persistence: { backend, ready } }`.
2. `status` remains constrained to `"ok"` or `"degraded"`.
3. `persistence.ready` remains a boolean reflecting readiness probe output.
4. `persistence.backend` accepts configuration-driven string labels and is not restricted to a single literal backend type.
5. Default behavior for existing clients remains `persistence.backend == "postgresql"` when no override is configured.

#### Scenario: Ready probe yields stable success contract

- Given: the readiness probe reports ready
- When: a client calls `GET /health`
- Then: `status` is `"ok"`
- And: `persistence.ready` is `true`
- And: `persistence.backend` is present as a string label

#### Scenario: Not-ready probe yields stable degraded contract

- Given: the readiness probe reports not ready
- When: a client calls `GET /health`
- Then: `status` is `"degraded"`
- And: `persistence.ready` is `false`
- And: the response keeps the same top-level and nested field names
