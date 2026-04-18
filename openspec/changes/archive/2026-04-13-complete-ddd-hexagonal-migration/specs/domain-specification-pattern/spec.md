## MODIFIED Requirements

### Requirement: Domain specifications SHALL be composable

The system SHALL provide specification primitives that can be composed with logical operators for reusable domain rule evaluation, and these primitives SHALL be the single source of truth for move-rule logic consumed by application and persistence adapters.

#### Scenario: Compose two rules with logical AND

- **WHEN** two specifications are combined with logical AND
- **THEN** the composed specification SHALL return true only if both child specifications are satisfied

#### Scenario: Rule behavior is consistent across adapters

- **WHEN** in-memory and SQL persistence adapters evaluate the same movement candidate
- **THEN** both adapters SHALL produce equivalent decisions based on the same domain specification implementation
