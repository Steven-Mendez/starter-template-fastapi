# result-pattern Specification

## Purpose

Provide an explicit success-or-failure type for domain code so failures are values, not ambiguous sentinels, and can be composed and mapped to HTTP responses.

## Requirements

### Requirement: Result distinguishes success from failure

The system SHALL provide discriminated success and failure types `Ok` and `Err` and a type alias `Result[T, E]` equivalent to `Ok[T] | Err[E]`, where `Ok` carries a value of type `T` and `Err` carries an error of type `E`.

#### Scenario: Ok holds a value

- **WHEN** a value is wrapped in `Ok`
- **THEN** predicates report success and unwrapping yields that value

#### Scenario: Err holds an error

- **WHEN** an error is wrapped in `Err`
- **THEN** predicates report failure and unwrapping the error yields that value

### Requirement: Result combinators behave predictably

The system SHALL provide operations to transform successful values (`map`), transform errors (`map_err`), chain fallible steps (`and_then`), and unwrap or fail fast (`unwrap`, `unwrap_err`, `expect`, `expect_err`).

#### Scenario: map leaves Err unchanged

- **WHEN** `map` is applied to an `Err`
- **THEN** the result is the same error without invoking the mapping function on a success value

#### Scenario: and_then short-circuits on Err

- **WHEN** `and_then` is applied to an `Err`
- **THEN** the callback is not called and the `Err` is returned

### Requirement: Kanban fallible operations use Result

The Kanban store SHALL use `Result` for operations that can fail (for example missing board, column, or card), and the HTTP layer SHALL map `Err` values to the same status codes and message bodies as before this change.

#### Scenario: Missing resource still 404

- **WHEN** a client requests a non-existent board, column, or card through the HTTP API
- **THEN** the response status code SHALL be `404` and the detail message SHALL remain consistent with prior behavior
