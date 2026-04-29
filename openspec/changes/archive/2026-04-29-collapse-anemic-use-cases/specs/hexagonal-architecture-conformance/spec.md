## ADDED Requirements

### Requirement: Use cases are single orchestration units

Every application use case under `src/application/use_cases/` SHALL be
declared as a class whose `execute` method contains the orchestration
body. The class SHALL NOT delegate the entire body of `execute` to a
free function defined in another module.

#### Scenario: execute body contains the orchestration
- **WHEN** a contributor opens any `src/application/use_cases/*/<verb>.py`
  file
- **THEN** the class's `execute` method contains the actual repository
  calls, domain interactions, mapping, and `Result` construction —
  not a single line forwarding all arguments to an external function

#### Scenario: no handle_* free functions in commands or queries packages
- **WHEN** a contributor inspects `src/application/commands/` and
  `src/application/queries/`
- **THEN** no module defines a function whose name starts with
  `handle_`. The packages contain only command and query DTO classes
  (and helpers strictly local to those DTOs)

#### Scenario: API dependencies still construct use case classes
- **WHEN** `src/api/dependencies/use_cases.py` resolves a use case for a
  FastAPI route
- **THEN** it instantiates a `<Verb>UseCase` class with the required
  ports and returns the instance — the call surface for routes
  remains `use_case.execute(command_or_query)`

### Requirement: Architecture test forbids reintroducing the pass-through shape

The `tests/architecture/` suite SHALL include a test, marked
`@pytest.mark.architecture`, that fails if either of the following
holds:

- A class declared under `src/application/use_cases/` whose name ends
  in `UseCase` has an `execute` method whose entire body is a single
  `return <call>` statement where `<call>` targets a function whose
  name starts with `handle_` defined in another module.
- A module under `src/application/commands/` or
  `src/application/queries/` defines a function whose name starts with
  `handle_`.

#### Scenario: pass-through use case fails the suite
- **WHEN** a contributor reintroduces a `handle_*` function and a
  use case class whose `execute` body is `return handle_<verb>(...)`
- **THEN** running `uv run pytest tests/architecture -m architecture`
  exits non-zero with a failure that names the offending class and
  module

#### Scenario: free handler function in commands fails the suite
- **WHEN** a contributor adds `def handle_create_card(...)` to a module
  under `src/application/commands/`
- **THEN** the architecture test fails and names the offending module

#### Scenario: legitimate orchestration passes the suite
- **WHEN** a use case class's `execute` method calls multiple methods
  on injected ports, performs domain interactions, and returns a
  `Result`
- **THEN** the test passes regardless of the number of statements
  inside `execute`
