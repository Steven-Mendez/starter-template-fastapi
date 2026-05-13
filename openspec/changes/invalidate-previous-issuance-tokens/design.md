## Depends on

- `make-auth-flows-transactional` — this change wraps the invalidation step inside the same single-transaction Unit of Work that `make-auth-flows-transactional` extends to cover token issuance. Order: `make-auth-flows-transactional` first, then this change adds `invalidate_unused_tokens_for(...)` to the same in-transaction writer.

## Conflicts with

- `schedule-token-cleanup`: both touch the `auth_internal_tokens` table. No logical conflict — this change stamps `used_at` on existing rows; `schedule-token-cleanup` later deletes rows whose `used_at`/`expires_at` is past the retention window. Order: this change first; `schedule-token-cleanup` second (its purge clause already covers the stamped rows).
- `harden-auth-defense-in-depth`, `clean-architecture-seams`: also edit `request_password_reset.py` and `request_email_verification.py`. Order: `clean-architecture-seams` first (port relocation), then `make-auth-flows-transactional`, then this change, then `harden-auth-defense-in-depth`.

## Context

Token re-issuance should make older tokens dead. Today they coexist; the latest is just the latest, not "the only valid one". The fix is one extra SQL statement inside the same transaction.

## Decisions

- **Invalidate by stamping `used_at`, not deleting**: leaves an audit trail and preserves the schedule-token-cleanup purge window. Rationale: deletion erases evidence; the retention purge in `schedule-token-cleanup` handles eventual removal.
- **Run inside the same Unit of Work as the new-token insert**: atomic re-issuance. Rationale: prevents a window where both old and new tokens are simultaneously valid (or simultaneously invalid).

## Risks / Trade-offs

- **Risk**: a user clicked "send again" before realizing the first email arrived; they then use the first token (now invalidated). Mitigation: UX expectation is "the most recent email is the live one" — standard across major SaaS.

## Migration

Single PR. Backwards compatible.
