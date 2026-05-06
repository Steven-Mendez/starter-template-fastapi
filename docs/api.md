# API Reference

This document describes the HTTP API exposed by the current source code.

## Base URL

Local development default:

```text
http://localhost:8000
```

Kanban resources are mounted under `/api`. The readiness endpoint is mounted at
`/health`.

## OpenAPI

When `APP_ENABLE_DOCS=true`, Swagger UI and ReDoc are available at:

- `/docs`
- `/redoc`

The current code does not disable `/openapi.json` when `APP_ENABLE_DOCS=false`.

## Authentication

Read endpoints do not require authentication.

Write endpoints require `X-API-Key` only when `APP_WRITE_API_KEY` is configured.
If `APP_WRITE_API_KEY` is empty or unset, write endpoints are open.

Protected write endpoints:

- `POST /api/boards`
- `PATCH /api/boards/{board_id}`
- `DELETE /api/boards/{board_id}`
- `POST /api/boards/{board_id}/columns`
- `DELETE /api/columns/{column_id}`
- `POST /api/columns/{column_id}/cards`
- `PATCH /api/cards/{card_id}`

Header format:

```http
X-API-Key: <APP_WRITE_API_KEY>
```

Invalid or missing API keys return `401` with Problem Details JSON.

## Common Response Headers

Every response includes `X-Request-ID`.

- If the request provides `X-Request-ID`, the response echoes it.
- If the request omits `X-Request-ID`, the middleware generates a UUID string.

## Error Format

Errors are rendered as `application/problem+json`.

Common fields:

| Field | Type | Description |
| --- | --- | --- |
| `type` | string | Problem type URI, or `about:blank` for generic HTTP errors. |
| `title` | string | HTTP status phrase or explicit validation title. |
| `status` | integer | HTTP status code. |
| `instance` | string | Request URL. |
| `detail` | string | Human-readable detail when available. |
| `request_id` | string | Request ID from middleware when available. |
| `code` | string | Application error code for application-level errors. |
| `errors` | array | Validation error details for request validation failures. |

Example application error:

```json
{
  "type": "https://starter-template-fastapi.dev/problems/board-not-found",
  "title": "Not Found",
  "status": 404,
  "instance": "http://localhost:8000/api/boards/00000000-0000-0000-0000-000000000000",
  "detail": "Board not found",
  "code": "board_not_found",
  "request_id": "abc-123"
}
```

## Status Codes

| Status | Meaning |
| --- | --- |
| `200` | Successful read, patch, or health response. |
| `201` | Board, column, or card created. |
| `204` | Board or column deleted. |
| `401` | Write API key is configured and the request did not provide the correct `X-API-Key`. |
| `404` | Board, column, or card was not found. |
| `409` | Card move violated a domain rule. |
| `422` | Request validation failed, or a patch request contained no effective changes. |
| `500` | Unmapped domain error or unhandled server error. |
| `503` | Application or feature container was not available. |

Path IDs are parsed as UUIDs by FastAPI. Invalid UUID path values return `422`.

## Schemas

### BoardCreate

| Field | Type | Required | Validation |
| --- | --- | --- | --- |
| `title` | string | yes | Length 1 to 500. |

### BoardUpdate

| Field | Type | Required | Validation |
| --- | --- | --- | --- |
| `title` | string or null | no | When present and not null, length 1 to 500. |

An empty board patch returns application error `patch_no_changes` with `422`.

### BoardSummary

| Field | Type |
| --- | --- |
| `id` | string |
| `title` | string |
| `created_at` | datetime |

### BoardDetail

| Field | Type |
| --- | --- |
| `id` | string |
| `title` | string |
| `created_at` | datetime |
| `columns` | array of `ColumnRead` |

### ColumnCreate

| Field | Type | Required | Validation |
| --- | --- | --- | --- |
| `title` | string | yes | Length 1 to 500. |

### ColumnRead

| Field | Type |
| --- | --- |
| `id` | string |
| `board_id` | string |
| `title` | string |
| `position` | integer |
| `cards` | array of `CardRead` |

### CardCreate

| Field | Type | Required | Validation |
| --- | --- | --- | --- |
| `title` | string | yes | Length 1 to 500. |
| `description` | string or null | no | No explicit length limit in code. |
| `priority` | `low`, `medium`, or `high` | no | Defaults to `medium`. |
| `due_at` | datetime or null | no | Parsed by Pydantic. |

### CardUpdate

| Field | Type | Required | Validation |
| --- | --- | --- | --- |
| `title` | string or null | no | When present and not null, length 1 to 500. |
| `description` | string or null | no | No explicit length limit in code. |
| `column_id` | UUID or null | no | Target column for moving a card. |
| `position` | integer or null | no | Must be greater than or equal to 0 when present. |
| `priority` | `low`, `medium`, or `high` | no | Updates card priority. |
| `due_at` | datetime or null | no | A present `null` clears the due date. |

An empty card patch returns application error `patch_no_changes` with `422`.

### CardRead

| Field | Type |
| --- | --- |
| `id` | string |
| `column_id` | string |
| `title` | string |
| `description` | string or null |
| `position` | integer |
| `priority` | `low`, `medium`, or `high` |
| `due_at` | datetime or null |

### HealthRead

| Field | Type |
| --- | --- |
| `status` | `ok` or `degraded` |
| `persistence.backend` | string |
| `persistence.ready` | boolean |

## Endpoints

### GET /

Returns a service status payload.

Response `200`:

```json
{
  "name": "starter-template-fastapi",
  "message": "FastAPI service is running."
}
```

### GET /health

Returns readiness information.

Response `200` when persistence is ready:

```json
{
  "status": "ok",
  "persistence": {
    "backend": "postgresql",
    "ready": true
  }
}
```

Response `200` when persistence is not ready:

```json
{
  "status": "degraded",
  "persistence": {
    "backend": "postgresql",
    "ready": false
  }
}
```

### POST /api/boards

Creates a board.

Request:

```json
{
  "title": "Roadmap"
}
```

Response `201`:

```json
{
  "id": "00000000-0000-0000-0000-000000000001",
  "title": "Roadmap",
  "created_at": "2026-01-01T12:00:00Z"
}
```

### GET /api/boards

Lists board summaries.

Response `200`:

```json
[
  {
    "id": "00000000-0000-0000-0000-000000000001",
    "title": "Roadmap",
    "created_at": "2026-01-01T12:00:00Z"
  }
]
```

### GET /api/boards/{board_id}

Gets a board with columns and cards.

Response `200`:

```json
{
  "id": "00000000-0000-0000-0000-000000000001",
  "title": "Roadmap",
  "created_at": "2026-01-01T12:00:00Z",
  "columns": [
    {
      "id": "00000000-0000-0000-0000-000000000002",
      "board_id": "00000000-0000-0000-0000-000000000001",
      "title": "To Do",
      "position": 0,
      "cards": []
    }
  ]
}
```

Errors:

- `404` with `code=board_not_found` when the board does not exist.

### PATCH /api/boards/{board_id}

Renames a board.

Request:

```json
{
  "title": "Updated roadmap"
}
```

Response `200` is a `BoardSummary`.

Errors:

- `404` with `code=board_not_found` when the board does not exist.
- `422` with `code=patch_no_changes` when no fields are provided.

### DELETE /api/boards/{board_id}

Deletes a board. Columns and cards are removed by database cascade behavior.

Response `204` has no body.

Errors:

- `404` with `code=board_not_found` when the board does not exist.

### POST /api/boards/{board_id}/columns

Creates a column at the next position in a board.

Request:

```json
{
  "title": "To Do"
}
```

Response `201`:

```json
{
  "id": "00000000-0000-0000-0000-000000000002",
  "board_id": "00000000-0000-0000-0000-000000000001",
  "title": "To Do",
  "position": 0,
  "cards": []
}
```

Errors:

- `404` with `code=board_not_found` when the board does not exist.

### DELETE /api/columns/{column_id}

Deletes a column and recalculates remaining column positions.

Response `204` has no body.

Errors:

- `404` with `code=column_not_found` when the column does not exist.

### POST /api/columns/{column_id}/cards

Creates a card in a column.

Request:

```json
{
  "title": "Write API docs",
  "description": "Document current routes and errors",
  "priority": "high",
  "due_at": "2026-12-01T00:00:00Z"
}
```

Response `201`:

```json
{
  "id": "00000000-0000-0000-0000-000000000003",
  "column_id": "00000000-0000-0000-0000-000000000002",
  "title": "Write API docs",
  "description": "Document current routes and errors",
  "position": 0,
  "priority": "high",
  "due_at": "2026-12-01T00:00:00Z"
}
```

Errors:

- `404` with `code=column_not_found` when the column does not exist.

### GET /api/cards/{card_id}

Gets one card.

Response `200` is a `CardRead`.

Errors:

- `404` with `code=card_not_found` when the card does not exist.

### PATCH /api/cards/{card_id}

Updates card fields and optionally moves the card.

Rename and change priority:

```json
{
  "title": "Publish API docs",
  "priority": "medium"
}
```

Clear due date:

```json
{
  "due_at": null
}
```

Move to another column at position 0:

```json
{
  "column_id": "00000000-0000-0000-0000-000000000004",
  "position": 0
}
```

Response `200` is a `CardRead`.

Errors:

- `404` with `code=card_not_found` when the card does not exist.
- `409` with `code=invalid_card_move` when a move violates domain rules.
- `422` with `code=patch_no_changes` when no fields are provided.

## Curl Examples

With no write API key configured:

```bash
curl -s -X POST http://localhost:8000/api/boards \
  -H 'Content-Type: application/json' \
  -d '{"title":"Roadmap"}'
```

With `APP_WRITE_API_KEY=secret`:

```bash
curl -s -X POST http://localhost:8000/api/boards \
  -H 'Content-Type: application/json' \
  -H 'X-API-Key: secret' \
  -d '{"title":"Roadmap"}'
```
