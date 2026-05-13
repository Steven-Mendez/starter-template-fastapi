## Depends on

- `invalidate-previous-issuance-tokens` (recommended) — once that change is in, the purge clause cleanly sweeps stamped-`used_at` rows past the retention window. Not a hard build dep but conceptually paired.

## Conflicts with

- `invalidate-previous-issuance-tokens`: both touch the `auth_internal_tokens` table. Order: `invalidate-previous-issuance-tokens` first (stamps `used_at`), then this change (purges rows past retention).
- `add-outbox-retention-prune`, `add-graceful-shutdown`, `propagate-trace-context-through-jobs`, `clean-user-assets-on-deactivate`: all register cron jobs in `src/worker.py`. Merge-friction only — distinct cron registrations.

## Context

Long-lived projects accumulate token rows that are by definition no longer useful. The fix is a small cron job; the retention window is a settings knob.

## Decisions

- **Default retention 7 days**: enough to investigate "did the user really log out at time X?" incidents; short enough to keep tables small.
- **Cron via arq**: same machinery as the outbox relay; no new infrastructure.
- **Batched delete (10k chunks)**: avoids long-running locks on a multi-million-row purge.
- **One use case operates on both tables**: `PurgeExpiredTokens.execute(retention_days)` calls into two repo methods (`delete_expired_refresh_tokens`, `delete_expired_internal_tokens`). Rationale: same retention window, same operational pattern.

## Risks / Trade-offs

- **Risk**: an over-aggressive retention deletes evidence ops needs for an investigation. Mitigation: configurable; default of 7 days is conservative.

## Migration

Single PR. Rollback: stop the cron; past purges don't undo, but the next deploy can extend retention to recover going forward.
