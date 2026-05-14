## Depends on

- None hard. Composes with `harden-rate-limiting` (per-account lockout) which dampens any residual DOS surface from the equalized-cost branches.

## Conflicts with

- `harden-rate-limiting`, `strengthen-production-validators`: all three add entries to `AuthenticationSettings.validate_production`. No logical conflict — merge friction only (separate appends).
- `invalidate-previous-issuance-tokens`, `clean-architecture-seams`: also edit `request_password_reset.py` and `request_email_verification.py`. Order: this change last so the equalized-cost branches wrap the already-transactional issuance path introduced by `make-auth-flows-transactional` + `invalidate-previous-issuance-tokens`.
- `expose-domain-metrics`, `improve-otel-instrumentation`: also edit `login_user.py`. Merge-friction only.

## Context

This proposal collects three small auth-surface hardenings that share a common theme: "looks correct, leaks information through a side channel that the existing tests don't measure". None is a critical CVE; together they materially slow down a determined enumeration + credential-stuffing attack, especially when combined with the rate-limit hardening landed in `harden-rate-limiting`.

## Goals / Non-Goals

**Goals**
- Login-time DB-roundtrip count is identical for hit and miss; verify is called against a fixed-cost dummy hash on miss using a constant-time comparison.
- Cookie-bearing state-changing routes require an explicit origin signal (Origin or Referer); plain `samesite=none` configurations are refused in production.
- Reset-token issuance latency is comparable across known vs unknown emails via a fixed-cost dummy work path — no `time.sleep`, no shadow DB writes.

**Non-Goals**
- Constant-time everything. We're closing latency *channels* by equalizing major branches.
- Anti-enumeration cosmetics like "always return 200 OK" — the current code already does that. The gap is timing.

## Decisions

### Decision 1: Equalize via constant-time comparison + fixed dummy hash on miss

- **Chosen**: on the no-user branch of `LoginUser`, call `verify_password(FIXED_DUMMY_ARGON2_HASH, supplied_password)` exactly once. The Argon2 verify call dominates wall-clock (~150 ms). Compare the boolean outcome to `False` via `hmac.compare_digest`-style constant-time equality on the resulting verification result so branch selection is not observable. Always issue the same number of DB roundtrips (`get_credential_for_user` invoked once in both branches via a `_NoCredentialUserId` sentinel returning `None`).
- **Rationale**: Argon2 is the dominant cost; matching it on the miss path collapses the timing channel without adding sleeps or shadow writes.
- **Rejected**: `time.sleep(uniform(...))` — observable in worker thread counts, easy to defeat with sustained traffic.
- **Rejected**: chasing exact wall-clock parity. Network jitter dwarfs the few-ms residual once Argon2 is matched.

### Decision 2: Require Origin OR Referer; refuse `samesite=none` in prod

- **Chosen**: `_enforce_cookie_origin` accepts `Referer` as a fallback when `Origin` is absent; refuses with 403 when both are missing AND the refresh cookie is present. Production validator refuses `auth_cookie_samesite="none"`.
- **Rationale**: SameSite=strict + Origin/Referer check covers the cross-site POST threat without introducing CSRF token plumbing.
- **Rejected**: a custom CSRF token (double-submit cookie). Adds protocol complexity for negligible additional protection given the SameSite default.

### Decision 3: Reset/verify issuance — fixed-cost dummy hash on the unknown-email branch (no shadow path, no sleep)

- **Chosen**: on the unknown-email branch of `RequestPasswordReset` and `RequestEmailVerification`, run `verify_password(FIXED_DUMMY_ARGON2_HASH, request.email)` exactly once. This is the same primitive used in `LoginUser` and dominates wall-clock by an order of magnitude. No DB writes, no sleep, no rollback transaction.
- **Rationale**: simplest closed timing surface that matches the dominant cost of the known-email branch (which also performs Argon2-class work via audit + token-row writes). Avoids the doubled write traffic of a shadow path and avoids the thread-count observability of `time.sleep`.
- **Rejected**: a real shadow path performing equivalent DB work then rolling back. Doubles write traffic on the unknown-email branch and was flagged as "too invasive" in early review.
- **Rejected**: `time.sleep(uniform(low, high))`. Observable in worker thread counts; vulnerable to sustained-traffic DOS.

## Risks / Trade-offs

- **Risk**: `FIXED_DUMMY_ARGON2_HASH` is a known string; an attacker could differentiate hit/miss by observing which exact hash was verified. Mitigation: irrelevant — the attacker only observes wall-clock, not the comparison's input. The verify call always runs; the comparison is constant-time.
- **Risk**: requiring Origin OR Referer is mildly stricter than the current contract. Pathological clients (curl with no headers) that currently sail through now get 403. That's the right answer when a refresh cookie is on the request.

## Migration Plan

Single PR; no schema changes. Order:

1. Define `FIXED_DUMMY_ARGON2_HASH` module constant (use the existing pattern in `LoginUser`).
2. Login equalization (sentinel + always-one-verify + constant-time comparison).
3. Cookie-origin enforcement + `samesite=none` validator entry.
4. Reset/verify fixed-cost dummy hash on the unknown-email branch.
5. Tests.

Rollback: revert. No persistence side effects.
