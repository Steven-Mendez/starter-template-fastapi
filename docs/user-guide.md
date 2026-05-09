# User Guide

This guide shows how to use the Kanban API once the service is running.

## Start The Service Locally

```bash
cp .env.example .env
uv sync
docker compose up -d db
uv run alembic upgrade head
make dev
```

The examples use `http://localhost:8000`.

If `APP_WRITE_API_KEY` is set, add this header to write requests:

```http
X-API-Key: <APP_WRITE_API_KEY>
```

## Check Service Status

```bash
curl -s http://localhost:8000/
```

Expected response:

```json
{
  "name": "starter-template-fastapi",
  "message": "FastAPI service is running."
}
```

Check process liveness and dependency readiness:

```bash
curl -s http://localhost:8000/health/live
curl -s http://localhost:8000/health/ready
```

`/health/live` returns `ok` when the process is accepting requests.
`/health/ready` returns `ok` when dependencies are ready and `503` when any
readiness check is degraded.

## Create A Board

```bash
curl -s -X POST http://localhost:8000/api/boards \
  -H 'Content-Type: application/json' \
  -d '{"title":"Roadmap"}'
```

Save the returned `id`. Later examples use `$BOARD_ID`.

## List Boards

```bash
curl -s http://localhost:8000/api/boards
```

The response is an array of board summaries.

## Get A Board

```bash
curl -s http://localhost:8000/api/boards/$BOARD_ID
```

The response includes the board, its columns, and cards inside each column.

## Rename A Board

```bash
curl -s -X PATCH http://localhost:8000/api/boards/$BOARD_ID \
  -H 'Content-Type: application/json' \
  -d '{"title":"Updated roadmap"}'
```

An empty body returns `422` with `code=patch_no_changes`.

## Add A Column

```bash
curl -s -X POST http://localhost:8000/api/boards/$BOARD_ID/columns \
  -H 'Content-Type: application/json' \
  -d '{"title":"To Do"}'
```

Columns are appended at the next available position. Save the returned `id` as
`$COLUMN_ID`.

## Create A Card

```bash
curl -s -X POST http://localhost:8000/api/columns/$COLUMN_ID/cards \
  -H 'Content-Type: application/json' \
  -d '{"title":"Write docs","description":"Document the current API","priority":"high","due_at":"2026-12-01T00:00:00Z"}'
```

Save the returned `id` as `$CARD_ID`.

`priority` can be `low`, `medium`, or `high`. If omitted, it defaults to
`medium`.

## Get A Card

```bash
curl -s http://localhost:8000/api/cards/$CARD_ID
```

## Update A Card

Rename a card:

```bash
curl -s -X PATCH http://localhost:8000/api/cards/$CARD_ID \
  -H 'Content-Type: application/json' \
  -d '{"title":"Publish docs"}'
```

Clear a due date:

```bash
curl -s -X PATCH http://localhost:8000/api/cards/$CARD_ID \
  -H 'Content-Type: application/json' \
  -d '{"due_at":null}'
```

Move a card to another column:

```bash
curl -s -X PATCH http://localhost:8000/api/cards/$CARD_ID \
  -H 'Content-Type: application/json' \
  -d '{"column_id":"00000000-0000-0000-0000-000000000004","position":0}'
```

The target column must belong to the same board. Invalid moves return `409` with
`code=invalid_card_move`.

## Delete A Column

```bash
curl -i -X DELETE http://localhost:8000/api/columns/$COLUMN_ID
```

The response status is `204`. Remaining column positions are recalculated.

## Delete A Board

```bash
curl -i -X DELETE http://localhost:8000/api/boards/$BOARD_ID
```

The response status is `204`. The database schema cascades deletion to child
columns and cards.

## Expected Behavior

- Board, column, and card titles must be non-empty and at most 500 characters.
- Card positions are zero-based.
- Requested card positions larger than the current column length are clamped to
  the end of the column.
- Omitting a field in a patch request leaves it unchanged.
- Sending `"due_at": null` in a card patch clears the due date.
- Read routes remain public even when `APP_WRITE_API_KEY` is set.

## Known Limitations

- There is no user account system.
- Write protection is a single optional API key.
- Board listing is not paginated.
- There is no endpoint to delete a single card.
- There is no endpoint to rename a column.
