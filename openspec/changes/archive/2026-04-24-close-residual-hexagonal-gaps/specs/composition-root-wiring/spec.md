## ADDED Requirements

### Requirement: API-facing container contracts SHALL expose ports, not repositories
The system SHALL restrict API-facing dependency contracts to driver-port handler dependencies, settings, and lifecycle-safe resource handles, and SHALL NOT expose driven repository accessors for route-level injection.

#### Scenario: Route dependencies resolve handlers without repository accessor
- **WHEN** API dependency providers are inspected
- **THEN** providers consumed by route handlers SHALL return command/query handler ports and SHALL NOT expose repository getter dependencies

#### Scenario: Concrete handler construction is composition-root owned
- **WHEN** command handler instances are created
- **THEN** construction SHALL happen in composition-root container wiring (for example handler factories) and SHALL NOT happen in API dependency modules

#### Scenario: Compatibility re-export modules preserve restricted boundary
- **WHEN** root-level compatibility modules re-export dependency helpers
- **THEN** they SHALL mirror the restricted API dependency contract and SHALL NOT reintroduce repository injection helpers
