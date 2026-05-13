## Context

The bootstrap-super-admin flow exists so a fresh deployment can create its first system admin without a human shell session. It must be idempotent: re-running the same env on the next deploy should be a no-op, not a duplicate-key error. The current implementation achieves idempotency by treating "email already exists" as equivalent to "admin already exists" — which is what makes the privilege escalation possible.

The use case lives in `authorization`; the credential check (the missing piece) lives in `authentication`. Those features cannot import each other directly, so the verifier has to be a port.

## Goals / Non-Goals

**Goals**
- Eliminate the silent-promotion path entirely. The default-deny posture is the contract.
- Keep the genuine idempotent path working: re-bootstrap with the same env is still safe.
- Preserve the cross-feature boundaries: `authorization` keeps owning the relationship write, `authentication` keeps owning credential verification.

**Non-Goals**
- A general-purpose role-promotion API. Bootstrap is a startup-time concern only.
- Replacing the password-based bootstrap with magic-link / passwordless. Out of scope.
- Refactoring `UserRegistrarPort` to drop the "lookup-or-create" shape; the shape is fine, just unsafe at the caller.

## Decisions

### Decision 1: Default-deny over default-allow

- **Chosen**: refuse promotion of an existing non-admin user unless `APP_AUTH_BOOTSTRAP_PROMOTE_EXISTING=true`. Operators who *want* to promote an existing user (e.g. they pre-created the account through some other channel) must consciously flip the flag and supply the user's actual password.
- **Rejected**: "warn but proceed" — keeps the privilege escalation latent.
- **Rejected**: refuse unconditionally even when `promote_existing=true`. There is a legitimate use case (the operator owns the account they're trying to promote), and locking it down further pushes operators toward worse workarounds (direct SQL).

### Decision 2: New `CredentialVerifierPort` instead of expanding `UserRegistrarPort`

- **Chosen**: a small new port owned by `authorization.application.ports.outbound`, implemented by `authentication`. Single method: `verify(user_id, password) -> Result[None, CredentialVerificationError]`.
- **Rejected**: extending `UserRegistrarPort` with a `verify_credential` method. That port lives in `users` and would force `users` to depend on credential-row knowledge it does not (and should not) have.
- **Rejected**: routing verification through `LoginUser` — that use case has side effects (rate-limit counters, audit events) that don't apply to startup-time verification.

### Decision 3: Audit event with structured `subevent`

- **Chosen**: a single event type `authz.system_admin_bootstrapped` with a discriminator field. Keeps the audit-event catalog small while preserving observability of which path fired.
- **Rejected**: two separate event types (`...created` and `...promoted_existing`). Operationally indistinguishable for ops dashboards; just doubles the constants.

## Risks / Trade-offs

- **Risk**: an operator who *did* rely on the silent-promotion behavior (e.g. they intentionally pre-created the user and expected the next deploy to promote them) sees a startup refusal post-upgrade. Mitigation: the audit log + startup log line explicitly mention the `promote_existing` flag and the password mismatch case, so the remediation is one env var away.
- **Risk**: introducing a new port adds surface area. Mitigation: the port is narrow (one method, one Result), and it slots into the same pattern as `AuditPort` and `UserRegistrarPort`.

## Migration Plan

Single PR; no DB migrations.

1. Land the new setting (default `false`) and the new port + verifier adapter.
2. Refactor `BootstrapSystemAdmin` with the new branching.
3. Wire from `src/main.py` and `src/features/authentication/management.py`.
4. Run `make ci`.
5. Smoke-test the four behavioral paths manually against the dev DB.

## Depends on

- None hard. The change targets the current bootstrap surface (`src/features/authentication/management.py`).

## Conflicts with

- `clean-architecture-seams` (architecture cluster) **relocates `src/features/authentication/management.py` to `src/cli/create_super_admin.py` and removes the original**. This change targets the **current** path; if `clean-architecture-seams` lands first, this change MUST be rebased and every reference to `src/features/authentication/management.py` becomes `src/cli/create_super_admin.py`. If this change lands first, the relocation in `clean-architecture-seams` carries the new `promote_existing` flag, `CredentialVerifierPort` wiring, and `BootstrapRefusedExistingUserError` / `BootstrapPasswordMismatchError` mapping through to the new CLI entrypoint unchanged.
- `make-authz-grant-atomic` (same cluster) edits the same `BootstrapSystemAdmin`. The two compose cleanly: that change adds `principal_cache.invalidate_user(...)` on the `Ok` path; this change adds new branches. Whichever lands second rebases and wires the cache invalidation through the create-and-grant (`subevent="created"`) and promote-existing (`subevent="promoted_existing"`) success paths. The idempotent no-op path has no cache to invalidate.
- `improve-otel-instrumentation` (observability cluster) decorates `BootstrapSystemAdmin` with `@traced`. Textual conflict only.
- `make-auth-flows-transactional` (auth cluster) ships a session-scoped `UserRegistrarPort` cousin and a new `CredentialVerifierPort`. Merge-friction only — both ports are constructed in `authentication/composition/container.py`.
