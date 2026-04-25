# Spec: Command Contract and Schema Wire Concerns

**Capability**: command-contracts
**Change**: fix-patch-command-wire-concerns

---

## ADDED Requirements

### Requirement: CC-03 — API mapper does not set `clear_due_at` when `due_at` is merely absent from payload


**Priority**: Medium

The `to_patch_card_input` mapper MUST distinguish between "due_at key not in payload" (do not touch) and "due_at key present and null" (clear it).

**Acceptance Criteria**:
1. `to_patch_card_input` sets `"clear_due_at": True` only when `"due_at"` key is present in `model_dump(exclude_unset=True)` AND its value is `None`.
2. `to_patch_card_input` sets `"clear_due_at": False` when `"due_at"` key is absent from the payload.
3. `to_patch_card_input` sets `"clear_due_at": False` when `"due_at"` is present with a non-null value (that case uses `due_at` field, not `clear_due_at`).

#### Scenario: Mapper sets `clear_due_at=True` only for explicit null

- Given: `CardUpdate` parsed from `{"due_at": null}` (field present, value null)
- When: `to_patch_card_input` is called
- Then: returned dict has `"clear_due_at": True` and `"due_at": None`

#### Scenario: Mapper leaves `clear_due_at=False` when field absent

- Given: `CardUpdate` parsed from `{}` (field absent)
- When: `to_patch_card_input` is called
- Then: returned dict has `"clear_due_at": False` and `"due_at": None`

## ADDED Requirements

### Requirement: CC-01 — `PatchCardCommand` expresses business intent, not HTTP wire semantics


**Priority**: Medium

`PatchCardCommand` MUST not contain fields that encode HTTP payload encoding details. The field `due_at_provided` communicates "was this JSON key present in the request body?" — a wire concern. It MUST be renamed to express the actual business intent: "should the due date be cleared?"

**Acceptance Criteria**:
1. `PatchCardCommand` has no field named `due_at_provided`.
2. `PatchCardCommand` has a field `clear_due_at: bool = False`.
3. `clear_due_at=True` means the caller explicitly requested that the due date be set to `None`.
4. `clear_due_at=False, due_at=None` means the caller did not include `due_at` in the patch and the handler does not modify the card's `due_at`.
5. `handle_patch_card` applies `due_at` update only when `command.clear_due_at is True` or `command.due_at is not None`.

#### Scenario: PATCH with `due_at: null` clears the due date

- Given: a card with `due_at = datetime(2030, 1, 1, tzinfo=utc)`
- When: `PATCH /api/cards/{id}` is called with body `{"due_at": null}`
- Then: response status is 200
- And: response `due_at` is `null`
- And: a subsequent `GET /api/cards/{id}` returns `due_at: null`

#### Scenario: PATCH without `due_at` field preserves the existing due date

- Given: a card with `due_at = datetime(2030, 1, 1, tzinfo=utc)`
- When: `PATCH /api/cards/{id}` is called with body `{"title": "Updated"}`
- Then: response status is 200
- And: response `due_at` equals `"2030-01-01T00:00:00+00:00"` (unchanged)

#### Scenario: `PatchCardCommand` constructed directly with `clear_due_at=True`

- Given: `KanbanCommandHandlers` with `FakeIdGenerator` and `FakeClock`
- When: `handle_patch_card(PatchCardCommand(card_id=id, clear_due_at=True, due_at=None))` is called on a card with `due_at` set
- Then: the returned `AppCard.due_at` is `None`

### Requirement: CC-02 — `CardUpdate.column_id` is validated as UUID at the HTTP boundary


**Priority**: Medium

`CardUpdate.column_id` MUST be typed as `UUID | None` so Pydantic validates UUID format before the request reaches the application layer.

**Acceptance Criteria**:
1. `CardUpdate.column_id` type annotation is `UUID | None`.
2. A request `PATCH /api/cards/{id}` with `{"column_id": "not-a-uuid"}` returns 422 with a problem-details response.
3. A request with `{"column_id": "valid-uuid-string"}` is accepted (Pydantic coerces valid UUID strings).
4. The API mapper converts the `UUID` value to `str` before constructing `PatchCardCommand.column_id`.

#### Scenario: Invalid UUID in column_id body field returns 422

- Given: a valid card ID
- When: `PATCH /api/cards/{card_id}` is called with body `{"column_id": "definitely-not-a-uuid"}`
- Then: response status is 422
- And: response content-type is `application/problem+json`
- And: response body contains an `errors` array identifying the `column_id` field

#### Scenario: Valid UUID string in column_id body field is accepted

- Given: a valid card ID and a valid UUID string for a column
- When: `PATCH /api/cards/{card_id}` is called with body `{"column_id": "00000000-0000-4000-8000-000000000001"}`
- Then: response status is not 422 (may be 404 if column not found, but not a validation error)
