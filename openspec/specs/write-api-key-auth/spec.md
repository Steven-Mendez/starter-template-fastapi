# write-api-key-auth Specification

## Purpose
Protect mutating Kanban API operations at the HTTP adapter boundary using a configurable API key so write access can be restricted without coupling authentication concerns into application or domain layers.

## Requirements

### Requirement: WAKA-01 - Configurable write API key governs edge protection mode

**Priority**: High

The system MUST expose an application setting for write API key protection that keeps write-auth enablement configuration-driven and disabled by default.

**Acceptance Criteria**:
1. A configuration setting exists for a write API key and can be set via application settings/environment wiring.
2. When the write API key setting is unset, mutating API routes continue to behave as they did before this change.
3. When the write API key setting is set, mutating API routes require an `X-API-Key` header match before invoking write handlers.
4. Authentication logic remains in API/dependency wiring and is not imported by application or domain modules.

#### Scenario: Write protection disabled when key is unset

- Given: application settings do not provide a write API key
- When: a client calls `POST /api/boards` without `X-API-Key`
- Then: the route is processed by normal command handling and does not fail authentication

#### Scenario: Write protection enabled when key is set

- Given: application settings provide write API key value `k1`
- When: a client calls a mutating route without `X-API-Key` or with a non-matching key
- Then: the response status is `401 Unauthorized`
- And: command handlers are not invoked

### Requirement: WAKA-02 - Only mutating Kanban routes enforce write API key

**Priority**: High

The system MUST enforce write API key validation on mutating Kanban routes (`POST`, `PATCH`, `DELETE`) and MUST NOT enforce it on read-only `GET` routes.

**Acceptance Criteria**:
1. `POST`, `PATCH`, and `DELETE` routes under `/api` for boards, columns, and cards return `401` when write key protection is enabled and the key is missing/incorrect.
2. The same mutating routes return their existing success status codes when the correct `X-API-Key` is provided.
3. Existing read routes (`GET /api/boards`, `GET /api/boards/{board_id}`, `GET /api/cards/{card_id}`) remain accessible without `X-API-Key` even when write key protection is enabled.

#### Scenario: Mutating route denied without valid key

- Given: write key protection is enabled with API key `k1`
- When: a client calls `PATCH /api/cards/{card_id}` with no key header
- Then: the response status is `401 Unauthorized`

#### Scenario: Mutating route allowed with valid key

- Given: write key protection is enabled with API key `k1`
- When: a client calls `DELETE /api/boards/{board_id}` with header `X-API-Key: k1`
- Then: the response status is `204 No Content`

#### Scenario: Read routes remain open

- Given: write key protection is enabled with API key `k1`
- When: a client calls `GET /api/boards` without `X-API-Key`
- Then: the response status is `200 OK`
