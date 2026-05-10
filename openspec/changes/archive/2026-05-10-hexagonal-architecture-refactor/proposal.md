## Why

The `auth` feature was built with a flatter service model that diverges from the strict hexagonal ports-and-adapters structure that `kanban` follows, creating an inconsistency that makes the template harder to follow and the auth layer harder to test in isolation. Outbound ports already exist for auth (verified in `src/features/auth/application/ports/outbound/auth_repository.py`), but **inbound** ports do not — `AuthService` and `RBACService` are still monolithic classes that bundle every operation. A leftover `services.py` re-export shim and an implicit `request.state.actor_id` convention with no typed contract are the remaining gaps.

## What Changes

- **Decompose `AuthService` and `RBACService` into per-use-case classes** under `src/features/auth/application/use_cases/auth/` and `use_cases/rbac/`, each a `@dataclass(slots=True)` implementing one inbound port.
- **Introduce inbound port protocols** in `src/features/auth/application/ports/inbound/` — one `Protocol` per use case (`RegisterUserPort`, `LoginUserPort`, `RefreshTokenPort`, `ResolvePrincipalFromAccessTokenPort`, ...). The existing outbound ports (`UserRepositoryPort`, `TokenRepositoryPort`, `RBACRepositoryPort`, `AuditRepositoryPort`, composite `AuthRepositoryPort`) are preserved; per-use-case classes accept the narrowest sub-protocol they need (Interface Segregation).
- **Adopt `Result[T, AuthError]` throughout the auth application boundary** — replace `raise InvalidCredentialsError(...)` returns inside the use cases with `Err(InvalidCredentialsError(...))`. Existing `AuthError` subclasses are preserved as the error payload — no enum is introduced.
- **Update auth HTTP adapters to `match Ok/Err`** — `auth.py` and `admin.py` use structural pattern matching instead of `try/except AuthError`.
- **Type the `request.state.actor_id` convention** — add `RequestState(TypedDict)` in `src/platform/api/request_state.py` with `actor_id: UUID | None` (matching the existing `Principal.user_id: UUID` type), plus typed `set_actor_id`/`get_actor_id` helpers; auth becomes the writer, kanban the reader.
- **Lift auth-protection wiring out of `main.py`** — move guard list construction into `auth/composition/wiring.py` as `make_auth_guard()`; `main.py` no longer imports `fastapi.Depends` for guard construction.
- **Delete `src/features/auth/application/services.py`** — the re-export shim is a migration artifact; tests already import from the split modules.
- **Update `_template` scaffold** to mirror the per-use-case pattern with a minimal in-memory fake.

## Capabilities

### New Capabilities

- `auth-hexagonal-ports`: Inbound `Protocol` per use case + per-use-case `@dataclass(slots=True)` implementations under `application/use_cases/`. Outbound ports already exist and are preserved (with their ISP slicing) — this capability documents the new inbound surface and the per-use-case decomposition that replaces `AuthService`/`RBACService`.
- `auth-result-type`: `Result[T, AuthError]` at the auth application boundary; HTTP adapters use `match Ok/Err`.
- `typed-request-state`: `RequestState(TypedDict)` in `platform/api/` with `actor_id: UUID | None` and typed setter/getter shared by the auth writer and kanban reader.
- `auth-guard-wiring`: `make_auth_guard()` helper in `auth/composition/wiring.py` so `main.py` no longer constructs the FastAPI `Depends` list directly.

### Modified Capabilities

*(No existing spec-level behavior changes — all public HTTP APIs are preserved.)*

## Impact

- `src/features/auth/application/` — new `ports/inbound/` subtree (outbound subtree already exists); `auth_service.py` and `rbac_service.py` decomposed into per-use-case classes under `use_cases/auth/` and `use_cases/rbac/`; `services.py` shim deleted.
- `src/features/auth/adapters/inbound/http/` — `auth.py` and `admin.py` updated to `match Ok/Err`; `dependencies.py` updated to call `set_actor_id(...)` instead of writing `request.state.actor_id` directly.
- `src/features/kanban/adapters/inbound/http/dependencies.py` — `get_actor_id` re-typed against `RequestState`/`UUID | None` (current shape is preserved; the change is just the typed source).
- `src/platform/api/request_state.py` — new module defining `RequestState(TypedDict)`, `set_actor_id`, `get_actor_id`.
- `src/features/auth/composition/container.py` — `auth_service`/`rbac_service` fields replaced by one field per use-case instance.
- `src/features/auth/composition/wiring.py` — gains `make_auth_guard()`.
- `src/main.py` — calls `make_auth_guard(auth_container)`; removes `Depends`/`get_current_principal` imports if no longer needed elsewhere.
- `src/features/_template/` — scaffold updated to reflect the per-use-case pattern.
- Import Linter contracts — no new contracts; all changes stay within existing layer rules.
- Public HTTP API — no breaking changes.
- **Out of scope (handled by `production-ready-template`):** moving `Principal` to `platform/shared/`, kanban RBAC, principal cache TTL default, auth use-case unit tests.
