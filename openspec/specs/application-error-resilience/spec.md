# application-error-resilience Specification

## Purpose
Prevent domain-to-application error translation drift from causing runtime `KeyError` and guarantee a stable fallback contract through the API layer.

## Requirements

### Requirement: AER-01 - Domain error translation is resilient to mapping drift

**Priority**: High

The application error translator MUST return a safe fallback `ApplicationError` when a domain error is not present in the translation map.

**Acceptance Criteria**:
1. `from_domain_error` does not raise `KeyError` when a domain error is missing from the map.
2. Existing mapped domain errors continue to resolve to their current `ApplicationError` values.
3. Missing mappings resolve to a dedicated fallback application error value.

#### Scenario: Known domain error mapping remains unchanged

- Given: a known `KanbanError` with an existing entry in the translation map
- When: `from_domain_error` is called
- Then: the corresponding existing `ApplicationError` is returned

#### Scenario: Missing mapping returns fallback instead of crashing

- Given: a `KanbanError` value is not present in the translation map due to map drift
- When: `from_domain_error` is called
- Then: no exception is raised
- And: the fallback `ApplicationError` is returned

### Requirement: AER-02 - Fallback application error has a stable API problem contract

**Priority**: High

The API adapter MUST map the fallback application error to a stable RFC 9457 problem response contract.

**Acceptance Criteria**:
1. The fallback `ApplicationError` has an explicit HTTP mapping entry.
2. The fallback maps to HTTP `500`.
3. The fallback response includes stable machine-readable metadata (`code` and `type`).

#### Scenario: Fallback application error maps to stable internal problem details

- Given: the API adapter receives the fallback `ApplicationError`
- When: it raises the HTTP exception for that application error
- Then: the status code is `500`
- And: the emitted `code` is the fallback error code
- And: the emitted `type` URI is the configured internal-domain-error URI
