# api-error-contract Specification

## Purpose
Define a stable API error contract for application-layer failures so every `ApplicationError` maps explicitly to HTTP semantics and RFC 9457 problem details include machine-readable metadata.

## Requirements

### Requirement: AEC-01 - Application errors map explicitly and exhaustively to HTTP semantics

**Priority**: High

The API adapter MUST define an explicit HTTP contract for every `ApplicationError` member and MUST NOT rely on a default fallback status mapping.

**Acceptance Criteria**:
1. The mapping defines a `status_code` and `type` URI for every `ApplicationError` member.
2. The mapping is exhaustive and fails fast if a new `ApplicationError` member is added without an HTTP contract entry.
3. `BOARD_NOT_FOUND`, `COLUMN_NOT_FOUND`, and `CARD_NOT_FOUND` map to `404`.
4. `INVALID_CARD_MOVE` maps to `409`.
5. `PATCH_NO_CHANGES` maps to `422`.

#### Scenario: Known not-found application error is translated

- Given: an API route receives `ApplicationError.CARD_NOT_FOUND`
- When: the adapter raises the HTTP error from that application error
- Then: the HTTP status is `404`
- And: the emitted problem details `type` is the configured card-not-found URI

#### Scenario: New application error without mapping is rejected at startup

- Given: an `ApplicationError` member exists without an HTTP contract mapping
- When: the API error mapping module is imported
- Then: startup fails fast with an explicit non-exhaustive mapping error

### Requirement: AEC-02 - Problem details include machine-readable application error metadata

**Priority**: High

For application-level failures, the API MUST emit `application/problem+json` payloads that keep human-readable text while adding stable machine-readable metadata.

**Acceptance Criteria**:
1. Application error responses include `type`, `status`, and `detail` fields per RFC 9457.
2. Application error responses include a machine-readable `code` field with the stable application error code.
3. The `detail` field remains the existing human-readable message for each error.
4. Non-application exceptions continue to use existing generic problem-details behavior.

#### Scenario: Conflict application error includes code and type

- Given: a request triggers `ApplicationError.INVALID_CARD_MOVE`
- When: the API responds with problem details
- Then: the response status is `409`
- And: the response `type` is the configured invalid-card-move URI
- And: the response `code` is `"invalid_card_move"`
- And: the response `detail` is `"Invalid card move"`

#### Scenario: Generic exception behavior is unchanged

- Given: a non-application runtime exception occurs in a request path
- When: the global exception handler emits a problem response
- Then: the response remains `500 Internal Server Error`
- And: the response uses the existing generic RFC 9457 payload shape
