# domain-command-validation Specification

## Purpose
Ensure PATCH command validation is owned by the application layer and patch mutations execute through domain intent methods instead of direct entity field mutation in handlers.

## Requirements

### Requirement: DCV-01 — PATCH commands reject empty/no-op updates in application handlers

**Priority**: High

Application command handlers MUST reject PATCH commands that do not carry any effective update intent, independent of HTTP adapter checks.

**Acceptance Criteria**:
1. `handle_patch_board` returns an application validation error when no board fields are provided.
2. `handle_patch_card` returns an application validation error when no card fields are provided and `clear_due_at` is false.
3. API PATCH endpoints map this application validation error to HTTP `422 Unprocessable Content` with a stable message.

#### Scenario: Board PATCH with empty payload is rejected by command handler

- Given: an existing board and a `PatchBoardCommand` with only `board_id`
- When: `handle_patch_board` is executed
- Then: it returns `ApplicationError.PATCH_NO_CHANGES`

#### Scenario: Card PATCH with empty payload is rejected by command handler

- Given: an existing card and a `PatchCardCommand` with only `card_id`
- When: `handle_patch_card` is executed
- Then: it returns `ApplicationError.PATCH_NO_CHANGES`

### Requirement: DCV-02 — Patch mutations use domain intent methods

**Priority**: High

Application handlers MUST call explicit domain methods for PATCH intent operations instead of mutating entity fields inline.

**Acceptance Criteria**:
1. Board rename operations use a `Board` intent method (for example, `rename`) rather than assigning `board.title` in the handler.
2. Card patch operations use a `Card` intent method (for example, `apply_patch`) rather than assigning card fields in the handler.
3. Domain tests cover these intent methods for positive update and due-date clear behavior.

#### Scenario: Board title update flows through domain intent

- Given: an existing board and a patch command with a new title
- When: the patch command handler runs
- Then: the board title is updated through the board rename method and persisted

#### Scenario: Card partial update flows through domain intent

- Given: an existing card and a patch command with title/priority updates
- When: the patch command handler runs
- Then: card fields are updated through the card patch intent method and persisted

### Requirement: DCV-03 — API adapters remain transport-focused for PATCH validation

**Priority**: Medium

HTTP routers MUST keep transport-level validation in schemas and delegate no-op business validation to application handlers.

**Acceptance Criteria**:
1. PATCH routers do not implement duplicate no-op business checks after command-level validation is introduced.
2. Schema-level validation still rejects malformed transport values (for example, invalid UUID in `column_id`).
3. Existing successful PATCH flows remain functional after moving no-op checks to application handlers.

#### Scenario: Router delegates empty PATCH payload validation downstream

- Given: a PATCH request with `{}` and valid route params
- When: the router builds the command and dispatches it
- Then: the handler returns a no-op validation error and the router maps it to HTTP 422
