# infrastructure-mapping-isolation Specification

## Purpose
TBD - created by archiving change hex-port-segregation-and-mapping. Update Purpose after archive.
## Requirements
### Requirement: Infrastructure Mapper Isolation
Infrastructure mapping modules MUST depend only on persistence models, domain models, and adapter-local types, and MUST NOT depend on application-layer DTO contracts.

#### Scenario: Persistence mapper does not import application contracts
- **WHEN** infrastructure persistence mappers are validated
- **THEN** they contain no imports from application contract modules

#### Scenario: Application DTO shaping occurs outside persistence adapter
- **WHEN** read data is prepared for inbound transport
- **THEN** transformation to application or transport DTOs occurs in application or inbound adapter mapping layers

### Requirement: Read-Model Boundary Consistency
The system MUST define a stable read-model contract between query adapters and query use cases.

#### Scenario: Query adapter returns read-model contract
- **WHEN** a query repository implementation returns list views
- **THEN** return types conform to the query read-model contract and remain independent of persistence table schemas
