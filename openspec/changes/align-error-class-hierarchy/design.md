## Depends on

(none) — this change is the root of the errors-http cluster. Every later change in the cluster (`add-stable-problem-types`, `enrich-validation-error-payload`, `declare-error-responses-in-openapi`, `preserve-error-response-headers`) consumes the `ApplicationError` taxonomy introduced here.

## Conflicts with

Same-file overlap on `src/app_platform/api/error_handlers.py` with `add-stable-problem-types`, `enrich-validation-error-payload`, `declare-error-responses-in-openapi`, `preserve-error-response-headers`, `add-error-reporting-seam`. Agreed merge order for the chain: `align-error-class-hierarchy → add-stable-problem-types → enrich-validation-error-payload → declare-error-responses-in-openapi → preserve-error-response-headers`. `add-error-reporting-seam` is independent; resolve textual collisions with `rebase` against whichever has landed.

Same-file overlap on `src/features/users/adapters/inbound/http/errors.py` with `hide-internal-fields-from-self-views` (out of cluster) — land this change first; the other change is mechanical.

## Context

CLAUDE.md and the code disagree about error shape. The Result-monad story works regardless, but readers (and tooling) benefit from one root class.

## Decisions

- **Root class in `app_platform.shared.errors`**: cross-cutting, no feature owns it. Final class name: `ApplicationError(Exception)`.
- **Each feature's base inherits from `ApplicationError`**:
  - `AuthError(ApplicationError)` (was `RuntimeError`)
  - `AuthorizationError(ApplicationError)` (was `RuntimeError`)
  - `EmailError(ApplicationError)` (was `Exception`)
  - `JobError(ApplicationError)` (was `Exception`)
  - `OutboxError(ApplicationError)` (was `Exception`)
  - `FileStorageError(ApplicationError)` (was `Exception`)
  - `UserError(ApplicationError)` (was `Enum`).
- **Subclass-per-case for `UserError`**: matches every other feature. Final subclass set: `UserNotFoundError` (replaces `UserError.NOT_FOUND`), `UserAlreadyExistsError` (replaces `UserError.DUPLICATE_EMAIL`). Rationale: one subclass per *existing* enum value, no speculative additions. `DeactivateUser` does not currently distinguish "already inactive" — it unconditionally calls `set_active`. The auth feature already owns `InactiveUserError(AuthError)` for "authenticated request targets an inactive user", so a sibling `UserDeactivatedError` would duplicate without adding signal.
- **Constructors take positional args only, no required kwargs**: rationale: `Exception.__reduce__` round-trips positional `args` for free, which keeps `pickle` working across the arq Redis boundary.
- **Pickling contract enforced by test**: arq's path is the only place this matters today, but the rule applies forever once tested.
- **HTTP error mapping migrates from enum matching to `isinstance` matching**: rationale: the new hierarchy is the canonical type discriminator; `add-stable-problem-types` will hang URN selection off the same `isinstance` chain.

## Risks / Trade-offs

- **Risk**: HTTP error mapping needs a small refactor to switch from enum matching to `isinstance` matching. Mechanical change.
- **Risk**: callers of `UserError.DUPLICATE_EMAIL`/`UserError.NOT_FOUND` enum values break. Mitigation: replace at the small number of call sites in a single PR.

## Migration

Single PR. Rollback: revert.
