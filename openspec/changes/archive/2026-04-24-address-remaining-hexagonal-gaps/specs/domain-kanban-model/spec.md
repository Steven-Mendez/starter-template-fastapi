## MODIFIED Requirements

### Requirement: Domain model SHALL represent business invariants directly
The system SHALL represent card movement and board-column ordering invariants through explicit domain behaviors on aggregate roots and entities, without fallback runtime introspection.

#### Scenario: Column deletion preserves contiguous ordering
- **WHEN** a column is removed from a board aggregate that still has other columns
- **THEN** remaining columns SHALL be reindexed to contiguous `position` values (`0..n-1`) as part of aggregate behavior

#### Scenario: Aggregate logic avoids private cross-entity API calls
- **WHEN** aggregate methods coordinate child-entity consistency work
- **THEN** they SHALL use public entity operations and SHALL NOT invoke underscore/private child methods directly
