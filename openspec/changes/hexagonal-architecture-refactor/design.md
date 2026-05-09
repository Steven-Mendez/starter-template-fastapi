## Context

The codebase has two active features: `kanban` (strict hexagonal ports-and-adapters) and `auth` (flatter service model). The divergence was intentional during initial construction but now creates two problems: the template is harder to follow because the two features teach different patterns, and the auth layer is harder to test in isolation because its application services are not behind inbound port interfaces.

Verification against the current codebase (2026-05-09):
- `src/features/auth/application/ports/outbound/auth_repository.py` already defines `UserRepositoryPort`, `TokenRepositoryPort`, `RBACRepositoryPort`, `AuditRepositoryPort`, and the composite `AuthRepositoryPort` with proper ISP slicing. **Outbound ports do not need to be introduced** — they need to be preserved and consumed correctly by the new use-case classes.
- `src/features/auth/application/services.py` is a re-export shim (imports `AuthService`, `RBACService`, `ensure_permissions`, `ensure_roles`, `PASSWORD_RESET_PURPOSE`, `EMAIL_VERIFY_PURPOSE`).
- `src/features/auth/adapters/inbound/http/dependencies.py:84` writes `request.state.actor_id = principal.user_id` directly. `principal.user_id` is a `UUID`. The kanban reader (`get_actor_id`) returns `UUID | None`.
- `src/main.py:96` constructs `require_auth = [Depends(get_current_principal)]` inline.

This design is additive and refactor-only: bring `auth` up to the same standard as `kanban` without changing any public HTTP contracts.

## Goals / Non-Goals

**Goals:**
- Give `auth`'s application layer the same `ports/inbound/` + `use_cases/<domain>/` structure as `kanban`
- Adopt `Result[T, AuthError]` at the auth application boundary; HTTP adapters use `match Ok/Err`
- Type the implicit `request.state.actor_id` convention (preserving its `UUID` type)
- Simplify `main.py` by moving auth-guard construction into `auth/composition/wiring.py`
- Delete the `application/services.py` re-export shim
- Update `_template` to reflect the per-use-case baseline
- All `make ci` gates pass before and after

**Non-Goals:**
- Changing any public HTTP API shape or status codes
- Rewriting the domain layer or changing domain models
- Replacing SQLModel persistence adapters or modifying outbound port shapes
- Adding new feature capabilities (new endpoints, new RBAC roles, etc.)
- Changing the kanban feature (it is already correct)
- Migrating to a different DI framework
- Moving `Principal` to `platform/shared/` (deferred to `production-ready-template`)

## Decisions

### Decision 1: Inbound ports as `Protocol` classes, mirroring kanban
**Choice:** Use `typing.Protocol` (structural subtyping) for all new inbound port interfaces.
**Rationale:** Existing kanban ports use `Protocol`; consistency avoids teaching two patterns. Protocols also let fakes be registered without inheritance.
**Alternative considered:** `abc.ABC`. Rejected — heavier, requires inheritance.

### Decision 2: Per-use-case `@dataclass(slots=True)` classes
**Choice:** Decompose `AuthService` (registration, login, refresh, logout, password reset request/confirm, email verification request/confirm, principal-from-access-token) and `RBACService` (assign role, remove role, grant permission, revoke permission, seed initial data, bootstrap super admin) into one `@dataclass(slots=True)` class per operation. Each implements a single inbound port. Each accepts only the outbound sub-protocols it actually uses (e.g., `RegisterUser` takes `UserRepositoryPort + AuditRepositoryPort`, not the composite).
**Rationale:** Mirrors kanban's `use_cases/board/create_board.py` pattern exactly. Dependency injection becomes explicit and per-operation.
**Alternative considered:** Keep `AuthService` as a facade behind a single port. Rejected — the shim pattern is what we're trying to remove.

### Decision 3: `Result[T, AuthError]` carrying existing `AuthError` subclass instances
**Choice:** Use cases return `Result[T, AuthError]` from `src/platform/shared/result.py`. The error payload is an instance of the existing `AuthError` subclass hierarchy (`InvalidCredentialsError`, `DuplicateEmailError`, `StaleTokenError`, etc.). No enum is introduced.
**Rationale:** Preserves the existing error vocabulary and the existing `raise_http_from_auth_error` mapping. The mechanical change is `raise X(...)` → `return Err(X(...))`. Type checkers see the concrete subclass through `Result[T, AuthError]`.
**Alternative considered:** Convert errors into an `AuthError` enum. Rejected — would require rewriting `errors.py` and the HTTP error map; out of scope.

### Decision 4: `RequestState` is a `TypedDict` with `actor_id: UUID | None`
**Choice:** `class RequestState(TypedDict): actor_id: UUID | None` in `src/platform/api/request_state.py`. Helpers `set_actor_id(request, actor_id)` and `get_actor_id(request) -> UUID | None`. Auth writes via `set_actor_id`; kanban reads via `get_actor_id`. The reader preserves the existing `getattr` semantics so deployments without auth wiring still resolve to `None`.
**Rationale:** `TypedDict` works with FastAPI's `Request.state` (`SimpleNamespace`-like). The accessor gives mypy a target without changing runtime behavior. Using `UUID | None` matches `Principal.user_id: UUID` already in `auth/application/types.py`; using `str | None` would force a stringify/parse roundtrip on every request.
**Alternative considered:** A full `Protocol` for the state object. Overkill.

### Decision 5: `make_auth_guard()` returns a dependency list
**Choice:** `auth/composition/wiring.py` exposes `make_auth_guard(container: AuthContainer) -> list[params.Depends]`. The list is `[Depends(get_current_principal)]` (the same dependency function the codebase already uses); the wrapper exists so `main.py` does not import FastAPI primitives for this purpose.
**Rationale:** Removes the `fastapi.Depends` import from `main.py` for guard construction. `main.py` becomes a pure wiring script.
**Alternative considered:** Pass the container to the route-mounting function and derive the guard internally. Overly clever; the list-of-Depends pattern is already used by `mount_kanban_routes`.

### Decision 6: Delete `services.py` shim without deprecation
**Choice:** Delete `src/features/auth/application/services.py` outright in this change.
**Rationale:** Internal module, no external callers. Tests import directly from the split modules. Keeping it perpetuates ambiguity about the canonical import path.
**Alternative considered:** Mark deprecated. Rejected — internal module, no public contract to deprecate.

## Risks / Trade-offs

**[Risk] Per-use-case refactor is a large diff in `auth/application/`.**
→ Mitigation: implement one use case at a time, running `make test` after each. The e2e suite covers the full auth HTTP flow.

**[Risk] Deleting `services.py` may break imports not found by grep.**
→ Mitigation: run `grep -rn "from src.features.auth.application.services\|application\.services\b" src/` before deletion. Update any callers in the same commit.

**[Risk] Switching `get_current_principal` to return `Result` is harder than other use cases because it is consumed by FastAPI directly.**
→ Mitigation: keep `get_current_principal` as a thin adapter that calls `ResolvePrincipalFromAccessTokenPort.execute(...)`, matches `Ok/Err`, and raises HTTP errors as it does today. The use case itself returns `Result`; the FastAPI dependency is the boundary that translates.

**[Risk] `TypedDict` cast for `request.state` is not enforced at runtime.**
→ Mitigation: acceptable — the goal is static analysis. The accessor returns `None` for missing values (existing behavior).

**[Risk] Updating `_template` may confuse mid-development users.**
→ Mitigation: `_template` is inert (not imported anywhere); zero runtime impact. Document in commit message.

## Migration Plan

1. Run `make ci` to capture baseline.
2. Implement in this order to keep tests green:
   a. `platform/api/request_state.py` — add `RequestState`, `set_actor_id`, `get_actor_id`.
   b. Update auth `dependencies.py` to call `set_actor_id`; update kanban `dependencies.py` to call `get_actor_id` (the function name stays the same; only the type source changes).
   c. `auth/composition/wiring.py` → `make_auth_guard()`; simplify `main.py`.
   d. Inbound port protocols under `auth/application/ports/inbound/`.
   e. Per-use-case classes under `auth/application/use_cases/auth/` and `use_cases/rbac/`, one at a time. Run `make test` after each. Each use case accepts only the narrowest outbound sub-protocol it needs.
   f. Update `AuthContainer` to expose per-use-case fields; update HTTP adapter handlers to call them.
   g. Switch handlers to `match Ok/Err`.
   h. Delete `services.py` shim.
   i. Update `_template` scaffold.
3. Run `make ci` (full gate).
4. Rollback: each step is independently revertible; no DB migrations.

## Open Questions

- Should `RBACService` operations also become per-use-case classes, or stay as a single `RBACService` (admin operations are less frequent)? **Leaning yes**, for consistency with the rest of the refactor. Confirmed in proposal.
- Should the `_template` scaffold include a working in-memory fake repository, or remain a minimal stub? **Leaning yes**, makes the scaffold immediately runnable.
