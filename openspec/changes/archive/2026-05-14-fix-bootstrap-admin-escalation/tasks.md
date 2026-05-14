## 1. Settings & configuration

- [x] 1.1 Add `auth_bootstrap_promote_existing: bool = False` to `AppSettings` (`src/app_platform/config/settings.py`) with the `APP_AUTH_BOOTSTRAP_PROMOTE_EXISTING` env-var binding.
- [x] 1.2 Project the new field into `AuthenticationSettings` (`src/features/authentication/composition/settings.py`).
- [x] 1.3 Append `APP_AUTH_BOOTSTRAP_PROMOTE_EXISTING=false` to `.env.example` with a comment explaining the default-deny intent and the password-verification safety check that runs when set to `true`.

## 2. CredentialVerifierPort

- [x] 2.1 Define `CredentialVerifierPort` as a Protocol in `src/features/authorization/application/ports/outbound/credential_verifier_port.py` with `verify(user_id: UUID, password: str) -> Result[None, CredentialVerificationError]`.
- [x] 2.2 Implement `SQLModelCredentialVerifierAdapter` in `src/features/authentication/adapters/outbound/credential_verifier/sqlmodel.py` that loads the user's `CredentialTable` row and runs the existing `PasswordHasher.verify(...)`. Emit zero audit events and zero rate-limit increments.
- [x] 2.3 Wire the adapter through composition.
  - [x] 2.3.a Construct `SQLModelCredentialVerifierAdapter` inside `src/features/authentication/composition/container.py` (alongside the existing `SQLModelAuditAdapter` construction).
  - [x] 2.3.b Expose it on the authentication container so `src/main.py` can pull it.
  - [x] 2.3.c Pass it into the authorization container in `src/main.py` (after the authentication container exists, before the authorization container is built) so `BootstrapSystemAdmin` can depend on it.

## 3. Use-case refactor — `BootstrapSystemAdmin`

- [x] 3.1 Change `BootstrapSystemAdmin.execute` signature from `def execute(self, *, email, password) -> UUID` (current `bootstrap_system_admin.py:37`) to `def execute(self, *, email, password) -> Result[UUID, BootstrapRefusedExistingUserError | BootstrapPasswordMismatchError]`. Add `promote_existing: bool` and `credential_verifier: CredentialVerifierPort` to the dataclass fields.
- [x] 3.2 Implement the branch order:
  - (a) Look up by email via `UserRegistrarPort` (existing call) — but split the current `register_or_lookup(...)` into two ports or two methods so "lookup-only" doesn't side-effect a registration on the not-found path. Concretely: add `lookup_by_email(email) -> UUID | None` to `UserRegistrarPort`; the current `register_or_lookup` stays for path (b).
  - (b) Not found → call `register_or_lookup(...)` (creates) → grant admin → emit audit event with `subevent="created"`.
  - (c) Found AND already `system:main#admin` (read via `AuthorizationPort.check(...)`) → return `Ok(user_id)` no-op, emit no audit event.
  - (d) Found AND not admin AND `promote_existing=false` → return `Err(BootstrapRefusedExistingUserError(user_id, email))`; write nothing; emit no audit event.
  - (e) Found AND not admin AND `promote_existing=true` → call `credential_verifier.verify(user.id, password)`; on `Ok` grant relationship + emit audit event with `subevent="promoted_existing"`; on `Err` return `Err(BootstrapPasswordMismatchError(user_id))` and write nothing.
- [x] 3.3 Define `BootstrapRefusedExistingUserError(AuthorizationError)` and `BootstrapPasswordMismatchError(AuthorizationError)` in `src/features/authorization/application/errors.py`. After `align-error-class-hierarchy` lands, both inherit from `ApplicationError` transitively via `AuthorizationError`.
- [x] 3.4 Update the bootstrap caller (`src/features/authentication/management.py:138-145` today, or `src/cli/create_super_admin.py` post-`clean-architecture-seams`):
  - On `Err(BootstrapRefusedExistingUserError)`: log a structured ERROR line including `user_id`, the configured email, and the remediation `Set APP_AUTH_BOOTSTRAP_PROMOTE_EXISTING=true and re-supply the user's actual password to opt in.`. `raise SystemExit(2)` so the deploy fails fast and visibly rather than starting without an admin.
  - On `Err(BootstrapPasswordMismatchError)`: log a structured ERROR line including `user_id` and `Bootstrap password did not match the existing user's credential — refusing to promote.`. `raise SystemExit(2)`.
  - On `Ok(_)`: continue startup as today.

## 4. Audit event

- [x] 4.1 Record the new event type string `authz.system_admin_bootstrapped`. (Note: there is no central `audit_events.py` catalog file today — event types are bare strings passed to `SQLModelAuditAdapter.record(event_type, ...)`. Either (a) introduce a small constants module under `src/features/authentication/application/` if a catalog is wanted, or (b) just document the new string alongside the existing `authz.bootstrap_admin_assigned` reference at `src/features/authorization/application/use_cases/bootstrap_system_admin.py:60`. Verify location.)
- [x] 4.2 Emit the event from `BootstrapSystemAdmin` on every successful grant (paths b and e), with payload fields `actor="system"`, `reason="bootstrap_on_startup"`, and `subevent: "created" | "promoted_existing"`.

## 5. Tests

- [x] 5.1 Unit: bootstrap with no existing user → user created, admin granted, audit event recorded with `subevent="created"`.
- [x] 5.2 Unit: bootstrap with existing non-admin user + `promote_existing=false` → returns `Err(BootstrapRefusedExistingUserError)`; assert no audit event was emitted; assert no relationship row was written.
- [x] 5.3 Unit: bootstrap with existing non-admin user + `promote_existing=true` + matching password → relationship granted; audit event recorded with `subevent="promoted_existing"`.
- [x] 5.4 Unit: bootstrap with existing non-admin user + `promote_existing=true` + wrong password → returns `Err(BootstrapPasswordMismatchError)`; assert nothing was written.
- [x] 5.5 Unit: bootstrap with existing user already holding `system:main#admin` → returns `Ok` no-op; assert no audit event was emitted; assert no relationship row was written.
- [x] 5.6 Integration (Postgres-backed): run bootstrap twice with the same env → confirm the second run hits branch `c` (idempotent no-op), not a duplicate promotion.

## 6. Docs

- [x] 6.1 Add `APP_AUTH_BOOTSTRAP_PROMOTE_EXISTING` to the "Key env vars (auth-related)" table in `CLAUDE.md`.
- [x] 6.2 Add a "Bootstrapping the first admin" section to `docs/operations.md` covering the four behavioral paths and the two new error types.
- [x] 6.3 Document in `docs/operations.md` "Production checklist" that the validator does NOT refuse `promote_existing=true` — operators must consciously enable it.

## 7. Wrap-up

- [x] 7.1 `make ci` green.
- [x] 7.2 Manual: spin up dev DB, register `victim@example.com` via `/auth/register`, then run a process with `APP_AUTH_BOOTSTRAP_SUPER_ADMIN_EMAIL=victim@example.com` and `APP_AUTH_BOOTSTRAP_PROMOTE_EXISTING` unset → confirm startup logs the refusal and the relationship was not written.
