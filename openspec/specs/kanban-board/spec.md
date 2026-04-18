# kanban-board Specification

## Purpose

REST API for in-memory Kanban boards: boards contain ordered columns; columns contain ordered cards. Cards can move between columns on the same board.

## Requirements

### Requirement: Boards can be created and listed

The system SHALL expose endpoints to create a board with a title and list all boards. Each board SHALL have a unique identifier and timestamps for creation. During the migration to hexagonal architecture, these HTTP contracts SHALL remain unchanged while orchestration moves behind application use cases.

#### Scenario: Create board returns 201 with board body

- **WHEN** a client sends `POST /api/boards` with JSON `{"title": "Sprint"}`
- **THEN** the response status code SHALL be `201`
- **THEN** the response body SHALL be JSON with `id`, `title` equal to `"Sprint"`, and `created_at`

#### Scenario: List boards after create

- **WHEN** a client sends `GET /api/boards`
- **THEN** the response status code SHALL be `200`
- **THEN** the response body SHALL be a JSON array containing the created board summary fields

#### Scenario: Endpoint contract remains stable during migration

- **WHEN** board routes are refactored to call application use cases
- **THEN** request and response payload shapes for create and list operations SHALL remain backward compatible

### Requirement: A single board can be read, updated, and deleted

The system SHALL allow fetching one board by id, updating its title, and deleting it.

#### Scenario: Get board returns 404 when missing

- **WHEN** a client sends `GET /api/boards/{id}` with an id that does not exist
- **THEN** the response status code SHALL be `404`

#### Scenario: Update board title

- **WHEN** a client sends `PATCH /api/boards/{id}` with `{"title": "Renamed"}` for an existing board
- **THEN** the response status code SHALL be `200`
- **THEN** subsequent `GET /api/boards/{id}` SHALL return title `"Renamed"`

#### Scenario: Delete board removes board

- **WHEN** a client sends `DELETE /api/boards/{id}` for an existing board
- **THEN** the response status code SHALL be `204`
- **THEN** a following `GET /api/boards/{id}` SHALL return `404`

### Requirement: Columns belong to a board and can be managed

The system SHALL allow adding ordered columns to a board, listing them as part of the board detail, updating and deleting columns.

#### Scenario: Add column to board

- **WHEN** a client sends `POST /api/boards/{board_id}/columns` with `{"title": "Doing"}` for an existing board
- **THEN** the response status code SHALL be `201`
- **THEN** the column SHALL include `id`, `board_id`, `title`, and `position`

#### Scenario: Board detail includes columns

- **WHEN** a client sends `GET /api/boards/{id}` after columns exist
- **THEN** the response SHALL include a `columns` array with those columns in `position` order

#### Scenario: Delete column cascades or rejects with clear behavior

- **WHEN** a client deletes a column that contains cards
- **THEN** the system SHALL either delete contained cards or reject the operation; behavior SHALL be consistent and documented in API responses (implementation: delete column and its cards)

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
