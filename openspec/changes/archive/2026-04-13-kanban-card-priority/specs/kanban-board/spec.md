## MODIFIED Requirements

### Requirement: Cards belong to columns and can be moved

The system SHALL allow creating cards in a column, updating fields (including `priority`), moving a card to another column with a position, and deleting a card. Cards in a column response SHALL be ordered by ascending `position` only; `priority` SHALL NOT affect that ordering (it is metadata for clients).

#### Scenario: Create card in column

- **WHEN** a client sends `POST /api/columns/{column_id}/cards` with `{"title": "Task A", "description": "Note"}` for an existing column
- **THEN** the response status code SHALL be `201`
- **THEN** the card SHALL include `id`, `column_id`, `title`, `description`, `position`, and `priority`
- **THEN** the `priority` SHALL be `medium` when the request omitted `priority`

#### Scenario: Create card with explicit priority

- **WHEN** a client sends `POST /api/columns/{column_id}/cards` with `{"title": "Task B", "description": null, "priority": "high"}` for an existing column
- **THEN** the response status code SHALL be `201`
- **THEN** the card SHALL include `"priority": "high"`

#### Scenario: Update card priority

- **WHEN** a client sends `PATCH /api/cards/{card_id}` with `{"priority": "low"}` for an existing card
- **THEN** the response status code SHALL be `200`
- **THEN** the card SHALL include `"priority": "low"`

#### Scenario: Move card to another column

- **WHEN** a client sends `PATCH /api/cards/{card_id}` with `{"column_id": "<other_column_id>"}` for an existing card
- **THEN** the response status code SHALL be `200`
- **THEN** the card's `column_id` SHALL match the target column

#### Scenario: Missing resource returns 404

- **WHEN** a client addresses a non-existent card, column, or board id
- **THEN** the response status code SHALL be `404` where applicable
