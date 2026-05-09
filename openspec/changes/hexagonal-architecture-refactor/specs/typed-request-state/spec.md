## ADDED Requirements

### Requirement: RequestState TypedDict defines the actor_id convention
A `RequestState` `TypedDict` SHALL be defined in `src/platform/api/request_state.py`. It SHALL declare `actor_id: UUID | None` (matching the existing `Principal.user_id` type used by the auth feature). This module SHALL NOT import from any `features` subpackage.

#### Scenario: RequestState is importable from platform.api
- **WHEN** `from src.platform.api.request_state import RequestState` is executed
- **THEN** the import succeeds with no error

#### Scenario: Platform does not import features
- **WHEN** Import Linter checks are run via `make lint-arch`
- **THEN** `src/platform/api/request_state` reports zero imports from `src/features`

### Requirement: Auth adapter writes actor_id through typed accessor
The auth HTTP adapter (`dependencies.py`) SHALL set `request.state.actor_id` using a typed setter `set_actor_id(request: Request, actor_id: UUID | None) -> None`. The current direct assignment in `get_current_principal` (`request.state.actor_id = principal.user_id`) SHALL be replaced with this helper.

#### Scenario: Auth dependency sets actor_id after principal resolution
- **WHEN** `get_current_principal()` resolves a valid JWT
- **THEN** `set_actor_id(request, principal.user_id)` is called and the stored value equals `principal.user_id` (a `UUID`)

### Requirement: Kanban adapter reads actor_id through typed accessor
The kanban HTTP adapter (`dependencies.py`) SHALL read `request.state.actor_id` via `get_actor_id(request) -> UUID | None`. The accessor SHALL preserve the existing `getattr(request.state, "actor_id", None)` semantics so deployments without auth wiring still resolve to `None`.

#### Scenario: Kanban dependency reads actor_id for authenticated request
- **WHEN** an authenticated request reaches a kanban route after auth has set `actor_id`
- **THEN** `get_actor_id(request)` returns the same `UUID` that auth set

#### Scenario: Kanban dependency handles missing actor_id gracefully
- **WHEN** `request.state.actor_id` was never written (anonymous deployment, no auth dependency mounted)
- **THEN** `get_actor_id(request)` returns `None` without raising

### Requirement: mypy verifies reader/writer agreement
Running `make typecheck` SHALL produce zero errors related to `request.state.actor_id` access in both auth and kanban adapters.

#### Scenario: Type check passes with no actor_id errors
- **WHEN** `make typecheck` is executed after the refactor
- **THEN** exit code is 0 and no errors reference `actor_id` or `RequestState`
