## MODIFIED Requirements

### Requirement: One Use Case Per Business Intent
The application layer MUST express each business intent as a single dedicated use-case class. Generic aggregator classes that hold multiple unrelated handlers (for example, a class with `handle_create_board`, `handle_patch_board`, and `handle_delete_board` methods on one object) are forbidden.

#### Scenario: New command introduces a dedicated use case
- **WHEN** a new command-side intent is added to the application layer
- **THEN** it is implemented as a class whose name ends in `UseCase`, lives in its own file under `src/application/use_cases/<aggregate>/<verb>_<noun>.py`, and exposes exactly one public method named `execute`

#### Scenario: New query introduces a dedicated use case
- **WHEN** a new query-side intent is added to the application layer
- **THEN** it is implemented as a class whose name ends in `UseCase`, lives in its own file under `src/application/use_cases/<aggregate>/<verb>_<noun>.py`, and exposes exactly one public method named `execute`

#### Scenario: Aggregator service object is rejected
- **WHEN** a class in `src/application/` declares two or more public methods that orchestrate distinct business intents (for example, both creation and deletion of an aggregate)
- **THEN** the conformance suite fails citing the `use-case-cohesion` capability
