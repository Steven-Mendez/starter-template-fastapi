## MODIFIED Requirements

### Requirement: Cards belong to columns and can be moved

The system SHALL allow creating cards in a column, updating fields (including `priority` and optional `due_at`), moving a card to another column with a position, and deleting a card. Cards in a column response SHALL be ordered by ascending `position` only; `priority` and `due_at` SHALL NOT affect that ordering (they are metadata for clients).

#### Scenario: Create card in column

- **WHEN** a client sends `POST /api/columns/{column_id}/cards` with `{"title": "Task A", "description": "Note"}` for an existing column
- **THEN** the response status code SHALL be `201`
- **THEN** the card SHALL include `id`, `column_id`, `title`, `description`, `position`, `priority`, and `due_at`
- **THEN** the `priority` SHALL be `medium` when the request omitted `priority`
- **THEN** the `due_at` SHALL be JSON `null` when the request omitted `due_at`

#### Scenario: Create card with explicit priority

- **WHEN** a client sends `POST /api/columns/{column_id}/cards` with `{"title": "Task B", "description": null, "priority": "high"}` for an existing column
- **THEN** the response status code SHALL be `201`
- **THEN** the card SHALL include `"priority": "high"`

#### Scenario: Create card with due_at

- **WHEN** a client sends `POST /api/columns/{column_id}/cards` with a body that includes `"due_at"` set to a valid ISO 8601 datetime string for an existing column
- **THEN** the response status code SHALL be `201`
- **THEN** the card response SHALL include the same logical instant as `due_at` (ISO 8601 in JSON)

#### Scenario: Update card priority

- **WHEN** a client sends `PATCH /api/cards/{card_id}` with `{"priority": "low"}` for an existing card
- **THEN** the response status code SHALL be `200`
- **THEN** the card SHALL include `"priority": "low"`

#### Scenario: Update card due_at and clear due_at

- **WHEN** a client sends `PATCH /api/cards/{card_id}` with `{"due_at": "<iso8601>"}` for an existing card
- **THEN** the response status code SHALL be `200`
- **THEN** the card SHALL include that `due_at` value

- **WHEN** a client sends `PATCH /api/cards/{card_id}` with `{"due_at": null}` for a card that previously had a non-null `due_at`
- **THEN** the response status code SHALL be `200`
- **THEN** the card SHALL include `due_at` as JSON `null`

#### Scenario: Move card to another column

- **WHEN** a client sends `PATCH /api/cards/{card_id}` with `{"column_id": "<other_column_id>"}` for an existing card
- **THEN** the response status code SHALL be `200`
- **THEN** the card's `column_id` SHALL match the target column

#### Scenario: Missing resource returns 404

- **WHEN** a client addresses a non-existent card, column, or board id
- **THEN** the response status code SHALL be `404` where applicable
