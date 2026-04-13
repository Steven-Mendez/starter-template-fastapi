## MODIFIED Requirements

### Requirement: Card updates distinguish invalid cross-board moves
The system SHALL represent an attempt to move a card to a column on a different board as a failure distinct from a simple missing id where useful for tests. The move rule SHALL be evaluated through domain specification objects.

#### Scenario: Cross-board column target yields invalid-move error
- **WHEN** `update_card` is asked to set `column_id` to a column that exists but belongs to another board than the card's current column
- **THEN** the result SHALL be `Err` with an error code for invalid move
