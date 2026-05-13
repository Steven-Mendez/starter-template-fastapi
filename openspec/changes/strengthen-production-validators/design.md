## Depends on

- `strengthen-test-contracts` (recommended) — adds tests for the three previously untested refusals. Not a hard build dep.

## Conflicts with

- `harden-rate-limiting`, `harden-auth-defense-in-depth`, `fix-bootstrap-admin-escalation`, `add-error-reporting-seam`: all append entries to `validate_production` across `AppSettings` / `AuthenticationSettings` / `ApiSettings`. No logical conflict — merge friction only.
- `improve-db-performance`: shares `src/app_platform/config/sub_settings.py`. Merge friction only.

## Context

`validate_production` is the project's last line of defense against unsafe configuration. It runs when `APP_ENVIRONMENT=production`, collects errors from every per-feature `validate_production` method, and refuses to start when any are present. The pattern is well-established; this proposal fills four content gaps and adds tests for three existing entries that lack coverage.

## Goals / Non-Goals

**Goals**
- Production REFUSES to start (not "warns and continues") when any of: JWT HS secret < 32 chars, wildcard `trusted_hosts`, missing/non-HTTPS `app_public_url`, `app_public_url` host outside `cors_origins`.
- Argon2 parameters are explicit and auditable in source.
- Every existing production-validator entry is covered by at least one unit test.

**Non-Goals**
- A full configuration-schema linter. Out of scope.
- Rehashing existing users' Argon2 password hashes when parameters drift.

## Decisions

### Decision 1: Refuse, do not warn

- **Chosen**: every new validator entry appends to the same error list that `AppSettings.validate_production()` already raises on. Boot fails fast.
- **Rationale**: "warn-only" is exactly how `auth_require_distributed_rate_limit=false` shipped silently broken. The validator's value comes from being a hard gate.
- **Rejected**: log-and-continue mode. The operator can read the error message and fix it; we do not need a soft mode.

### Decision 2: 32 bytes minimum for HS secrets, not "256 bits of entropy"

- **Chosen**: `len(auth_jwt_secret_key) >= 32` when `auth_jwt_algorithm` starts with `HS`.
- **Rationale**: pragmatic, easy to validate. The recommended command (`openssl rand -hex 32`) produces a 64-char hex string, well above the minimum.
- **Rejected**: entropy estimation. Heuristics over-flag legitimate base64 keys with repeated characters and under-flag low-entropy passphrases.

### Decision 3: `app_public_url` host must match a CORS origin

- **Chosen**: the validator parses the URL, requires HTTPS + non-empty host, and asserts the host appears in `cors_origins` (with scheme/port normalization).
- **Rationale**: the CORS origin list is the explicit "we trust this surface" declaration; password-reset and verification links land on that surface.
- **Rejected**: a separate `APP_PUBLIC_HOSTS` whitelist. Duplicates `cors_origins`.

### Decision 4: Argon2 parameters pinned in source, not env-tunable

- **Chosen**: `time_cost=3, memory_cost=65536, parallelism=4, hash_len=32, salt_len=16`. Matches OWASP 2024; ~150 ms per hash on a modern CPU.
- **Rationale**: env-tunable parameters drift across deploys (different envs = different costs); pinning in source makes rotation a deliberate, reviewable change.
- **Rejected**: env-var-driven parameters.

## Risks / Trade-offs

- **Risk**: a deploy with a known-good but short JWT secret (e.g. a 30-char passphrase) now fails to boot. Mitigation: docs and the validator's error message explicitly recommend `openssl rand -hex 32`.
- **Risk**: the `app_public_url`-host-in-`cors_origins` check rejects setups where the public URL host differs from any CORS origin. Mitigation: that topology already requires the public URL host in `APP_CORS_ORIGINS` for the SPA to call the API; if a third host is needed, operators add it.

## Migration Plan

Single PR; no schema changes.

1. Land the Argon2 pin first (smallest blast radius; no behavioral change for fresh hashes).
2. Add the four new validator entries.
3. Add the seven tests (three for existing, four for new).
4. `make ci`.

Rollback: revert. No persistence side effects.
