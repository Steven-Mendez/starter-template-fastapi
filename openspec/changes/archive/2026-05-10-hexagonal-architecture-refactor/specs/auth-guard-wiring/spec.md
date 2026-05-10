## ADDED Requirements

### Requirement: auth/composition/wiring.py exposes make_auth_guard helper
`src/features/auth/composition/wiring.py` SHALL expose a function `make_auth_guard(container: AuthContainer) -> list[params.Depends]` that returns a FastAPI dependency list enforcing JWT authentication. The returned list SHALL be equivalent to `[Depends(get_current_principal)]` where `get_current_principal` is the existing dependency in `src/features/auth/adapters/inbound/http/dependencies.py`.

#### Scenario: make_auth_guard returns a non-empty dependency list
- **WHEN** `make_auth_guard(container)` is called with a valid `AuthContainer`
- **THEN** the return value is a `list` with at least one `Depends` item

#### Scenario: Routes protected with make_auth_guard reject unauthenticated requests
- **WHEN** a route is mounted with `dependencies=make_auth_guard(container)` and an unauthenticated request arrives
- **THEN** the response is HTTP 401

#### Scenario: Routes protected with make_auth_guard accept valid JWT
- **WHEN** a route is mounted with `dependencies=make_auth_guard(container)` and a request carries a valid JWT
- **THEN** the route handler executes and `request.state.actor_id` is populated

### Requirement: main.py does not import FastAPI Depends for auth guard construction
`src/main.py` currently builds `require_auth = [Depends(get_current_principal)]` and passes it to `mount_kanban_routes`. After this change, `main.py` SHALL call `make_auth_guard(auth_container)` instead. The `from fastapi import Depends` and `from src.features.auth.adapters.inbound.http.dependencies import get_current_principal` imports SHALL be removed from `main.py` if they are no longer used elsewhere in the file.

Because `auth_container` is built inside the lifespan (it owns the DB pool), `make_auth_guard` SHALL accept either a built container or a settings/factory closure, OR the guard list SHALL be constructed using the dependency function reference (which does not require the container to exist at mount time). The implementation MAY keep the simpler form `[Depends(get_current_principal)]` so long as the wrapper helper is the single place this list is constructed.

#### Scenario: main.py imports no Depends for auth guard construction
- **WHEN** `grep "fastapi.*Depends" src/main.py` is run
- **THEN** zero matches related to auth guard construction are returned

#### Scenario: Kanban routes are still protected after refactor
- **WHEN** an unauthenticated request is sent to any kanban write endpoint
- **THEN** the response is HTTP 401, confirming the guard is active

#### Scenario: Kanban e2e tests pass with new wiring
- **WHEN** `make test-e2e` is run after the main.py simplification
- **THEN** all kanban e2e tests pass with exit code 0
