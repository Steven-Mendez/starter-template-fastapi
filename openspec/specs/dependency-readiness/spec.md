# dependency-readiness Specification

## Purpose
Define an explicit API-edge contract for dependency-container readiness failures so missing application wiring returns a service-availability problem response instead of a generic internal error.

## Requirements

### Requirement: DR-01 - Missing application container returns explicit service-availability error

**Priority**: High

When API dependencies resolve runtime wiring from `app.state`, a missing application container MUST raise an explicit dependency-readiness exception at the API edge.

**Acceptance Criteria**:
1. API dependency resolution does not raise a generic runtime exception for missing app container wiring.
2. The thrown exception is a dedicated API-edge dependency-readiness type.
3. The exception message clearly indicates that application container wiring is unavailable.

#### Scenario: Container wiring is missing during dependency resolution

- Given: an HTTP request reaches an API route that resolves handlers from `app.state.container`
- And: the application container has not been initialized or has been cleared
- When: dependency resolution executes at the API edge
- Then: the API layer raises the explicit dependency-readiness exception
- And: the exception indicates service unavailability due to missing container wiring

### Requirement: DR-02 - Dependency-readiness exception maps to RFC 9457 service unavailable response

**Priority**: High

The API error-handling layer MUST map the dependency-readiness exception to an RFC 9457 `application/problem+json` response with HTTP `503 Service Unavailable`.

**Acceptance Criteria**:
1. Responses use HTTP status `503`.
2. Responses keep the existing RFC 9457 payload shape (`type`, `title`, `status`, `instance`, `detail`).
3. Existing handling for non-readiness exceptions remains unchanged.

#### Scenario: API request hits missing container path

- Given: a request reaches an endpoint that requires dependency-container-backed handlers
- And: the app container is missing
- When: the request is processed
- Then: the response status is `503`
- And: the response `content-type` starts with `application/problem+json`
- And: the response problem payload includes the service-unavailable detail
- And: generic unhandled-exception behavior for unrelated failures stays `500`
