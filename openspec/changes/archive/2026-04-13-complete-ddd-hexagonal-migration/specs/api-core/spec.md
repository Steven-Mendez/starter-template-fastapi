## MODIFIED Requirements

### Requirement: Health endpoint for liveness

The system SHALL expose `GET /health` for liveness checks and return JSON indicating the service is running. Readiness checks used by this endpoint SHALL be resolved through composition-root-managed application dependencies and SHALL NOT require route handlers to import concrete persistence adapters directly. API handlers SHALL keep transport-only responsibilities and delegate orchestration/mapping to application boundary components.

#### Scenario: Load balancer probes health

- **WHEN** a client sends `GET /health`
- **THEN** the response status code SHALL be `200`
- **THEN** the response body SHALL be JSON and SHALL include a field indicating healthy status (for example `status` with value `ok`)

#### Scenario: Health route stays adapter-only

- **WHEN** health endpoint dependencies are inspected
- **THEN** the route handler SHALL depend on application/composition abstractions and SHALL NOT construct repository adapters inline
