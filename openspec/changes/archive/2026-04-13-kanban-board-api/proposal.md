## Why

The starter API needs a concrete domain feature to demonstrate patterns: validation with Pydantic, REST design, and testability. A Kanban board API is a familiar model (boards, columns, cards) that fits in-memory storage for prototyping and pairs cleanly with automated tests.

## What Changes

- Add a REST API under `/api` for boards, columns, and cards backed by an in-memory store (no database).
- Use Pydantic v2 models for request and response bodies and validation.
- Add automated tests that define behavior before or alongside implementation (TDD).

## Capabilities

### New Capabilities

- `kanban-board`: In-memory Kanban HTTP API for managing boards, columns, and cards (create, read, update, delete, and moving cards between columns).

### Modified Capabilities

- None.

## Impact

- **New Python package**: `kanban/` (schemas, store, router).
- **Dependencies**: `pydantic` declared explicitly for models; dev dependencies `pytest` and `httpx` for tests.
- **Application**: `main.py` mounts the Kanban router; existing `/` and `/health` unchanged.
