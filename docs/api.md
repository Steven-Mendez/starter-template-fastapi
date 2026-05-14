# API Reference

This document describes the HTTP API exposed by the current source code.

## Base URL

Local development default:

```text
http://localhost:8000
```

Kanban resources are mounted under `/api`. Health endpoints are mounted at
`/health/live`, `/health/ready`, and `/health`.

## OpenAPI

When `APP_ENABLE_DOCS=true`, Swagger UI and ReDoc are available at:

- `/docs`
- `/redoc`

`/openapi.json` is disabled together with the interactive docs when
`APP_ENABLE_DOCS=false`.

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

## Pagination

Admin list endpoints use **keyset pagination** rather than offsets, so
deep pages stay constant-time and remain correct under concurrent
inserts. The cursor is opaque to clients — treat it as a string and pass
it back unchanged.

### Cursor format

The cursor is the base64-URL-safe encoding of a tiny JSON payload:

```json
{"created_at": "2026-05-01T12:34:56+00:00", "id": "0192a3b4-..."}
```

Clients should not parse the cursor — the JSON shape may evolve. The
authoritative semantics are:

- A request with no cursor returns the first page.
- A response includes `next_cursor` (or `next_before` on the audit log)
  iff another page is available. The field is `null`/absent on the last
  page.
- Pass `next_cursor` back as `?cursor=<token>` to fetch the next page.
- Cursors that fail to decode return `400 Bad Request` (Problem Details)
  and no database query runs.

### Endpoints that paginate

| Endpoint | Query parameter | Response field |
| --- | --- | --- |
| `GET /admin/users` | `?cursor=<base64>` | `next_cursor` |
| `GET /admin/audit-log` | `?before=<base64>` | `next_before` (walks newest-first) |

Both endpoints accept a `?limit=<n>` parameter (default 100, max 500).
Each page contains up to `limit` rows ordered by `(created_at, id)` —
ascending for `/admin/users`, descending for `/admin/audit-log`.

## Error Format

Errors are rendered as `application/problem+json`.

Common fields:

| Field | Type | Description |
| --- | --- | --- |
| `type` | string | Stable Problem Type URN (see "Problem Type URNs" below), or `about:blank` for genuinely uncategorized errors. |
| `title` | string | HTTP status phrase or explicit validation title. |
| `status` | integer | HTTP status code. |
| `instance` | string | Request URL. |
| `detail` | string | Human-readable detail when available. |
| `request_id` | string | Request ID from middleware when available. |
| `code` | string | Application error code for application-level errors. |
| `violations` | array | Field-level validation failures for 422 responses; see "Violation shape" below. |

### Problem Type URNs

Per RFC 9457 §3.1, the `type` field SHOULD be a stable identifier that
clients can branch on without parsing the human-readable `detail`. This
service uses a project-scoped URN scheme:

```text
urn:problem:<domain>:<code>
```

where `<domain>` is a lower-kebab capability tag (`auth`, `authz`,
`validation`, `generic`) and `<code>` is a lower-kebab error slug. URN
values are stable across versions — new members may be added but
existing values are never renamed. `about:blank` remains the
spec-compliant fallback for genuinely uncategorized errors.

The canonical catalog is defined as the `ProblemType` enum in
`src/app_platform/api/problem_types.py`:

| URN | HTTP status | Produced by |
| --- | --- | --- |
| `urn:problem:auth:invalid-credentials` | `401` | `InvalidCredentialsError` (wrong password / unknown email on login or self-erase re-auth). |
| `urn:problem:auth:rate-limited` | `429` | `RateLimitExceededError` (login/register/password-reset throttling). |
| `urn:problem:auth:token-stale` | `401` | `StaleTokenError` (access token's `authz_version` is behind the current value — re-authenticate). |
| `urn:problem:auth:token-invalid` | `401` / `400` | `InvalidTokenError` (malformed/expired Bearer token) and `TokenAlreadyUsedError` (one-shot reset/verification token already consumed). |
| `urn:problem:auth:email-not-verified` | `403` | `EmailNotVerifiedError` (login attempt when verification is required). |
| `urn:problem:authz:permission-denied` | `403` | `NotAuthorizedError`, `PermissionDeniedError`, `InactiveUserError` (principal lacks the required relation on the resource, or account is inactive). |
| `urn:problem:validation:failed` | `422` | FastAPI `RequestValidationError` (malformed request body / query / path). |
| `urn:problem:generic:conflict` | `409` | `UserAlreadyExistsError`, `DuplicateEmailError`, `ConflictError`. |
| `urn:problem:generic:not-found` | `404` | `UserNotFoundError`, `NotFoundError`. |
| `about:blank` | varies | Genuinely uncategorized failures (configuration errors, unhandled exceptions, malformed cursors, internal 500s). |

### Violation shape (422 responses)

A `422 Unprocessable Content` response always carries a `violations`
array on the Problem Details body — one entry per failed field. This is
the RFC 9457 §3.1 "extension member" convention adapted to this
service's terminology (`violations` rather than `invalid_params`).

| Field | Type | Description |
| --- | --- | --- |
| `loc` | `list[str \| int]` | Canonical Pydantic location path for the failed field, preserving order and types (e.g. `["body", "address", "zip"]`, `["query", "page"]`). SDKs use this to route the failure back to the right form field. |
| `type` | `string` | Stable Pydantic error type (e.g. `missing`, `value_error`, `string_too_short`). Treat as a public contract — new types may appear, existing types are not renamed. |
| `msg` | `string` | Human-readable explanation. |
| `input` | `object \| null` | The offending input value. **Present only in non-production environments.** Omitted (key absent) when `APP_ENVIRONMENT=production` to avoid echoing secrets. |

The `loc`, `type`, and `msg` fields are identical across environments;
only `input` is environment-gated. Producers MUST treat `input` as a
debug aid — the same redaction rules used for log scrubbing apply when
it enters logs.

Example 422 body (development):

```json
{
  "type": "urn:problem:validation:failed",
  "title": "Unprocessable Content",
  "status": 422,
  "instance": "http://localhost:8000/me",
  "detail": "Validation failed: 2 field(s)",
  "request_id": "abc-123",
  "violations": [
    {
      "loc": ["body", "email"],
      "type": "value_error",
      "msg": "value is not a valid email address",
      "input": "not-an-email"
    },
    {
      "loc": ["body", "name"],
      "type": "missing",
      "msg": "Field required",
      "input": null
    }
  ]
}
```

In production, each entry contains only `loc`, `type`, and `msg`.

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
| `200` | Successful read, patch, liveness, or ready health response. |
| `201` | Board, column, or card created. |
| `204` | Board or column deleted. |
| `401` | Write API key is configured and the request did not provide the correct `X-API-Key`. |
| `404` | Board, column, or card was not found. |
| `409` | Card move violated a domain rule. |
| `422` | Request validation failed, or a patch request contained no effective changes. |
| `500` | Unmapped domain error or unhandled server error. |
| `503` | Application container was unavailable or readiness was degraded. |

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
| `auth.jwt_secret_configured` | boolean |
| `auth.principal_cache_ready` | boolean |
| `auth.rate_limiter_backend` | `in_memory` or `redis` |
| `auth.rate_limiter_ready` | boolean |
| `redis.configured` | boolean or omitted when Redis is not configured |
| `redis.ready` | boolean or omitted when Redis is not configured |

### HealthLive

| Field | Type |
| --- | --- |
| `status` | `ok` |

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

### GET /health/live

Returns process liveness. It does not check external dependencies.

Response `200`:

```json
{
  "status": "ok"
}
```

### GET /health/ready

Returns readiness information.

Response `200` when dependencies are ready:

```json
{
  "status": "ok",
  "persistence": {
    "backend": "postgresql",
    "ready": true
  },
  "auth": {
    "jwt_secret_configured": true,
    "principal_cache_ready": true,
    "rate_limiter_backend": "in_memory",
    "rate_limiter_ready": true
  }
}
```

Response `503` when any readiness check is degraded:

```json
{
  "status": "degraded",
  "persistence": {
    "backend": "postgresql",
    "ready": false
  },
  "auth": {
    "jwt_secret_configured": true,
    "principal_cache_ready": true,
    "rate_limiter_backend": "in_memory",
    "rate_limiter_ready": true
  }
}
```

### GET /health

Backward-compatible alias for `GET /health/ready`.

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

### DELETE /me

Deactivates the calling user's own account (soft delete). Authentication is
required via a Bearer access token.

Self-deactivation is destructive; in a single response cycle the server:

1. Revokes every server-side refresh-token family for the user, inside the
   same Unit of Work that flips ``is_active=False``. This is the durable
   defense — a subsequent ``POST /auth/refresh`` with a captured refresh
   token returns ``401``.
2. Clears the browser-side refresh cookie by emitting
   ``Set-Cookie: refresh_token=; Max-Age=0; Path=/auth`` on the response.
   Cookie attributes (path, secure, samesite) mirror the original
   ``Set-Cookie`` so the browser actually deletes the entry.

Response `204` has no body.

Errors:

- `401` when the access token is missing or invalid.
- `404` when the user record is missing (e.g. already hard-deleted).

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
