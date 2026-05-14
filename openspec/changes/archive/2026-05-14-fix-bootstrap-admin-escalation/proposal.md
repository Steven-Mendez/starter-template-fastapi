## Why

`BootstrapSystemAdmin` (`src/features/authorization/application/use_cases/bootstrap_system_admin.py:45-58`) calls `UserRegistrarPort.register_or_lookup(...)`, which — when an account with the configured email already exists — returns the existing user's id **without verifying the supplied password**. The use case then unconditionally writes the `system:main#admin` relationship for that user.

Concretely: an operator sets `APP_AUTH_BOOTSTRAP_SUPER_ADMIN_EMAIL=admin@yourco.com` on a production deploy. If an attacker (or a regular employee who self-registered with that email first) already owns the account, the next startup promotes them to system admin. The supplied bootstrap password is silently ignored. This is a privilege escalation, not a "harmless re-bootstrap": the only path today is the most dangerous one.

The flow was designed to be idempotent for the "we already created the admin last deploy" case. That goal is correct; the implementation conflates it with "any user with the matching email is implicitly trusted", which is wrong.

## What Changes

- Add an opt-in setting `APP_AUTH_BOOTSTRAP_PROMOTE_EXISTING` (default `false`) on `AuthenticationSettings`. When `false` (the default), `BootstrapSystemAdmin` MUST refuse to promote an account that already exists unless it is *already* `system:main#admin` (the idempotency case).
- When `APP_AUTH_BOOTSTRAP_PROMOTE_EXISTING=true`, the use case MUST first verify the supplied password against the existing credential row. Mismatch → refuse and log; do not promote.
- Emit an explicit audit event `authz.system_admin_bootstrapped` on every successful promotion (new user OR existing user), with `actor=system`, `reason=bootstrap_on_startup`, and a distinct subevent flag for the "promoted-existing" path.
- Update `.env.example` and `CLAUDE.md` to document the new flag and the safe defaults.

**Capabilities — Modified**
- `authorization`: the bootstrap-super-admin requirement is tightened to refuse silent promotion.
- `authentication`: a new audit event type is added.

**Capabilities — New**
- None.

## Impact

- **Code paths edited**:
  - `src/features/authorization/application/use_cases/bootstrap_system_admin.py`
  - `src/features/authorization/application/ports/outbound/credential_verifier_port.py` (new)
  - `src/features/authentication/adapters/outbound/credential_verifier/sqlmodel.py` (new — adapter implementing the port)
  - audit event catalog (no central file today — see tasks 4.1; verify location)
  - `src/features/authentication/composition/settings.py`
  - `src/app_platform/config/settings.py`
  - `src/main.py`
  - `src/features/authentication/management.py` (current location — see "Depends on" / "Conflicts with" for the planned relocation)
  - `.env.example`
  - `CLAUDE.md`
  - `docs/operations.md`
- **Migrations**: none.
- **Production**: deployments that **rely on the current accidental-promotion behavior break loudly at startup**. That is the intended outcome; the proposal documents the escape hatch (`APP_AUTH_BOOTSTRAP_PROMOTE_EXISTING=true` + matching password).
- **Tests**: 5 new unit tests (one per branch in the new decision tree) + 1 Postgres integration test (idempotent re-bootstrap).
- **Backwards compatibility**: a fresh-DB deploy with `APP_AUTH_BOOTSTRAP_SUPER_ADMIN_EMAIL/PASSWORD` continues to behave identically — no existing user, no refusal. The only deploys this breaks are the ones that were silently broken to begin with.

## Depends on

- None hard. This change targets the **current** path `src/features/authentication/management.py`.

## Conflicts with

- `clean-architecture-seams` (architecture cluster) — that change relocates `src/features/authentication/management.py` to `src/cli/create_super_admin.py`. If `clean-architecture-seams` lands first, this change MUST be rebased: every `src/features/authentication/management.py` reference in tasks and design becomes `src/cli/create_super_admin.py`. If this change lands first, `clean-architecture-seams` carries the bootstrap-flag wiring through to the new CLI entrypoint.
- `make-authz-grant-atomic` (same cluster) — both edit `BootstrapSystemAdmin`. The two changes compose: that change adds cache invalidation on success; this change adds new branches and a new port. Whichever lands second rebases and threads `principal_cache.invalidate_user(...)` through the create-and-grant and promote-existing success paths.
- `improve-otel-instrumentation` (observability cluster) — adds a `@traced` decorator to `BootstrapSystemAdmin`. Textual conflict only; no semantic interaction.
