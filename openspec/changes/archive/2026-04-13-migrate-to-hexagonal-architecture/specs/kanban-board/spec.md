## MODIFIED Requirements

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
