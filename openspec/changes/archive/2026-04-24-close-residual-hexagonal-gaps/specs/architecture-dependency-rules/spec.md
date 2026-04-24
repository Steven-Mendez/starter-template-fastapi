## MODIFIED Requirements

### Requirement: Dependency rule SHALL be enforceable by tests
The system SHALL provide automated architecture tests that enforce inward-only dependency direction (infrastructure -> application -> domain) for direct imports and transitive import paths, and SHALL include executable checks for inbound driver-port usage and driven-adapter surface drift.

#### Scenario: Forbidden direct import is detected
- **WHEN** a module in domain or application imports forbidden outer-layer modules
- **THEN** architecture tests SHALL fail with a clear boundary violation message

#### Scenario: Forbidden transitive dependency path is detected
- **WHEN** an API module reaches infrastructure through one or more intermediate modules
- **THEN** architecture tests SHALL fail and report the transitive module path causing the violation

#### Scenario: API-to-domain contract leakage is detected
- **WHEN** an API adapter module imports domain models, domain shared errors, or domain result modules
- **THEN** architecture tests SHALL fail and identify the offending import edge

#### Scenario: Inbound driver-port bypass is detected
- **WHEN** API route dependencies are analyzed
- **THEN** architecture tests SHALL fail if route handlers depend on repository injections or concrete handler classes instead of driver-port contracts

#### Scenario: Route-level container injection is detected
- **WHEN** API route signatures are analyzed
- **THEN** architecture tests SHALL fail if a route injects the app container contract directly

#### Scenario: API dependency module imports concrete handlers
- **WHEN** API dependency provider modules are analyzed
- **THEN** architecture tests SHALL fail if concrete application handler classes are imported instead of ports/factories

#### Scenario: Driven adapter surface drift is detected
- **WHEN** persistence adapter public methods are compared to driven repository port methods
- **THEN** architecture tests SHALL fail if extra non-port production methods are exposed

### Requirement: Architecture boundaries SHALL be explicit per layer
The system SHALL codify allowed and forbidden dependencies per layer, including import boundaries for API schema modules and dependency-provider modules.

#### Scenario: Allowed import matrix is validated in CI
- **WHEN** CI executes the unit suite
- **THEN** boundary checks SHALL validate imports for domain, application, API adapters, infrastructure modules, and root-level dependency modules used by `src/`

#### Scenario: API schema layer remains transport-owned
- **WHEN** modules under `src/api/schemas/*` are validated
- **THEN** those modules SHALL NOT import `src.application.contracts` directly

#### Scenario: Violation diagnostics are actionable
- **WHEN** boundary checks fail
- **THEN** output SHALL include violated rule, source module, and disallowed dependency target (or transitive path)
