## ADDED Requirements

### Requirement: Domain specifications SHALL be composable
The system SHALL provide specification primitives that can be composed with logical operators for reusable domain rule evaluation.

#### Scenario: Compose two rules with logical AND
- **WHEN** two specifications are combined with logical AND
- **THEN** the composed specification SHALL return true only if both child specifications are satisfied

### Requirement: Specifications SHALL evaluate explicit domain candidates
The system SHALL evaluate domain rules against explicit candidate objects instead of reading persistence state directly inside specification classes.

#### Scenario: Evaluate card movement candidate
- **WHEN** a card movement candidate is evaluated
- **THEN** specifications SHALL use only candidate fields required by the business rule
