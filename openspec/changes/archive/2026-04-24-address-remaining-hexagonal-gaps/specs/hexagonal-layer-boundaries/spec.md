## MODIFIED Requirements

### Requirement: Inbound adapters SHALL be transport-only
The system SHALL ensure API routes depend on focused handler/settings dependencies and SHALL forbid direct coupling to container-provider internals.

#### Scenario: Route does not depend on container provider callable
- **WHEN** route dependency metadata is inspected
- **THEN** no route SHALL depend directly on `get_app_container` (or equivalent container provider) as a route-level dependency
