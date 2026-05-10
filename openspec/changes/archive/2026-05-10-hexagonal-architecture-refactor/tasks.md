## 1. Baseline Gate

- [x] 1.1 Run `make ci` and confirm all gates pass; record output as the baseline
- [x] 1.2 Run `grep -rn "from src.features.auth.application.services\|application\.services\b" src/` and document any callers (zero is the expected state)

## 2. Typed Request State (platform/api)

- [x] 2.1 Create `src/platform/api/request_state.py` defining `class RequestState(TypedDict): actor_id: UUID | None`
- [x] 2.2 Add `set_actor_id(request: Request, actor_id: UUID | None) -> None` and `get_actor_id(request: Request) -> UUID | None` helpers in `request_state.py`; `get_actor_id` SHALL preserve the existing `getattr(request.state, "actor_id", None)` semantics
- [x] 2.3 Update `src/features/auth/adapters/inbound/http/dependencies.py:84` to call `set_actor_id(request, principal.user_id)` instead of writing `request.state.actor_id = principal.user_id`
- [x] 2.4 Update `src/features/kanban/adapters/inbound/http/dependencies.py:109` (`get_actor_id`) to delegate to `platform.api.request_state.get_actor_id` so the typed source is shared
- [x] 2.5 Run `make typecheck` — confirm zero new errors

## 3. Auth Guard Wiring (auth/composition)

- [x] 3.1 Add `make_auth_guard(container: AuthContainer) -> list[params.Depends]` in `src/features/auth/composition/wiring.py` returning `[Depends(get_current_principal)]`
- [x] 3.2 Update `src/main.py` to call `make_auth_guard(...)`; remove the `from fastapi import Depends` and `from src.features.auth.adapters.inbound.http.dependencies import get_current_principal` imports if no longer used
- [x] 3.3 Run `make test-e2e` — confirm all kanban and auth e2e tests pass

## 4. Auth Inbound Port Protocols

- [x] 4.1 Create `src/features/auth/application/ports/inbound/__init__.py`
- [x] 4.2 Create one inbound port per current `AuthService` operation:
  - `register_user_port.py` (`RegisterUserPort`)
  - `login_user_port.py` (`LoginUserPort`)
  - `refresh_token_port.py` (`RefreshTokenPort`)
  - `logout_user_port.py` (`LogoutUserPort`)
  - `request_password_reset_port.py` (`RequestPasswordResetPort`)
  - `confirm_password_reset_port.py` (`ConfirmPasswordResetPort`)
  - `request_email_verification_port.py` (`RequestEmailVerificationPort`)
  - `confirm_email_verification_port.py` (`ConfirmEmailVerificationPort`)
  - `resolve_principal_port.py` (`ResolvePrincipalFromAccessTokenPort`)
- [x] 4.3 Create one inbound port per current `RBACService` operation:
  - `assign_role_port.py`, `remove_role_port.py`
  - `grant_permission_port.py`, `revoke_permission_port.py`
  - `seed_initial_data_port.py`, `bootstrap_super_admin_port.py`
- [x] 4.4 Each port declares `execute(command) -> Result[T, AuthError]` (or `Result[None, AuthError]` where appropriate)
- [x] 4.5 Run `make lint-arch` — confirm no new Import Linter violations

## 5. Auth Use-Case Classes (one at a time)

- [x] 5.1 Create `src/features/auth/application/use_cases/__init__.py` with sub-packages `auth/` and `rbac/`
- [x] 5.2 `use_cases/auth/register_user.py` — `@dataclass(slots=True) RegisterUser` accepting `AuthRepositoryPort`; returns `Result[User, AuthError]`. Run `make test`.
- [x] 5.3 `use_cases/auth/login_user.py` — accepts `AuthRepositoryPort + AccessTokenService`; returns `Result[tuple[IssuedTokens, Principal], AuthError]`. Run `make test`.
- [x] 5.4 `use_cases/auth/refresh_token.py` — accepts `AuthRepositoryPort + AccessTokenService`; returns `Result[tuple[IssuedTokens, Principal], AuthError]`. Run `make test`.
- [x] 5.5 `use_cases/auth/logout_user.py` (`LogoutUser` + `LogoutAllSessions`) — accepts `AuthRepositoryPort`; returns `Result[None, AuthError]`. Run `make test`.
- [x] 5.6 `use_cases/auth/request_password_reset.py` and `confirm_password_reset.py`. Run `make test` after each.
- [x] 5.7 `use_cases/auth/request_email_verification.py` and `confirm_email_verification.py`. Run `make test` after each.
- [x] 5.8 `use_cases/auth/resolve_principal.py` — extracts `AuthService.principal_from_access_token`; returns `Result[Principal, AuthError]`. Run `make test`.
- [x] 5.9 `use_cases/rbac/` — `list_roles.py`, `list_users.py`, `create_role.py`, `update_role.py`, `list_permissions.py`, `create_permission.py`, `assign_role_permission.py`, `remove_role_permission.py`, `assign_user_role.py`, `remove_user_role.py`, `list_audit_events.py`, `seed_initial_data.py`, `bootstrap_super_admin.py`. Run `make test` after each.

## 6. Auth HTTP Adapters → match Ok/Err

- [x] 6.1 Update `src/features/auth/adapters/inbound/http/auth.py` — replace `try/except AuthError` with `match result: case Ok(v): ... case Err(e): raise_http_from_auth_error(e)` in each handler
- [x] 6.2 Update `src/features/auth/adapters/inbound/http/admin.py` — same pattern for admin handlers
- [x] 6.3 Update `get_current_principal` in `dependencies.py` — call `container.resolve_principal.execute(token)`, match `Ok/Err`, raise via `raise_http_from_auth_error`; removed `try/except AuthError` block
- [x] 6.4 Verify `errors.py` covers all `AuthError` subclasses returned by the new use cases
- [x] 6.5 Run `make test-e2e` — confirm all auth HTTP flows still return correct status codes

## 7. Update AuthContainer

- [x] 7.1 Update `src/features/auth/composition/container.py` — replaced `auth_service: AuthService` and `rbac_service: RBACService` with per-use-case fields
- [x] 7.2 Update `build_auth_container(...)` factory to inject collaborators into each use case
- [x] 7.3 Update `_run_auth_bootstrap` in `main.py` to call `auth.seed_initial_data.execute()` and `auth.bootstrap_super_admin.execute(...)`
- [x] 7.4 Update e2e test conftest to use new container fields (no changes needed to wiring.py)

## 8. Delete services.py Shim

- [x] 8.1 Run `grep -rn "from src.features.auth.application.services\|application\.services\b" src/` — confirmed zero callers before deletion
- [x] 8.2 Delete `src/features/auth/application/services.py`
- [x] 8.3 Delete `src/features/auth/application/auth_service.py` and `rbac_service.py`; updated all integration tests and management.py to use new use-case API
- [x] 8.4 Run `make test` — 201 passed

## 9. Update _template Scaffold

- [x] 9.1 `src/features/_template/application/ports/inbound/get_example.py` — already existed with `GetExampleUseCasePort(Protocol)`
- [x] 9.2 `src/features/_template/application/ports/outbound/example_repository.py` — already existed with `ExampleRepositoryPort(Protocol)`
- [x] 9.3 `src/features/_template/application/use_cases/get_example.py` — already existed with `@dataclass(slots=True) GetExampleUseCase` returning `Result`
- [x] 9.4 Added `src/features/_template/tests/fakes/fake_repository.py` — minimal `FakeExampleRepository`
- [x] 9.5 Confirmed zero external imports of `_template`

## 10. Final Gate

- [x] 10.1 Run `make lint-arch` — 12/12 contracts kept, zero violations
- [x] 10.2 Run `make typecheck` — zero mypy errors (344 source files)
- [x] 10.3 Run `make test` — 201 passed, 29 deselected
- [x] 10.4 Run `make test-integration` — 29 passed
- [x] 10.5 Run `make ci` — full gate green: lint ✓, arch lint ✓, typecheck ✓, 201 unit+e2e ✓, 29 integration ✓
