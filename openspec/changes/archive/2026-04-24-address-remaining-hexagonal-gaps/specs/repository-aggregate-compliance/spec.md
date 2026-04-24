## MODIFIED Requirements

### Requirement: Repositories SHALL manage Data implicitly through the Aggregate Root
The system SHALL enforce aggregate-consistent persistence semantics when saving `Board` state, including normalized ordering for child collections after add/remove/move operations.

#### Scenario: Saved board reflects contiguous column positions
- **WHEN** a board with deleted/reordered columns is persisted
- **THEN** subsequent reads SHALL return columns with contiguous positions and stable board-local ordering semantics
