## Context

The repository today has three active features (`authentication`, `authorization`, `kanban`) plus an inert `_template` scaffold. `authentication` is overloaded: it owns identity (user table, password hashing, registration) *and* sessions (tokens, refresh, password reset). `kanban` is the demo feature any consumer will delete on day one. Common backend infrastructure that every project needs — transactional email, background jobs, file storage — is not modeled at all. The repo's stated promise ("starter template") does not match its current shape.

This design lays out the transformation into a true starter: a small core of `authentication` + `users` + `authorization`, a live `_template`, and three new infrastructure features (`email`, `background-jobs`, `file-storage`) that ship as scaffolding with port-and-adapter shapes ready to be wired into any consumer feature.

The change is large but follows a pattern the team has already executed twice (the original RBAC→ReBAC split and the more recent `authentication`/`authorization` split — commits `b526a34` and `aea9e82`). The same playbook applies here: define ports first, move state behind them, keep tests green at each step.

## Goals / Non-Goals

**Goals:**

- A developer can clone the repo, rename one feature, and start building product code in under an hour.
- The four cross-cutting concerns every backend needs (auth, users, authz, jobs+email+storage) are present as features the developer extends, not infrastructure they reinvent.
- `authentication` becomes small and focused: tokens, sessions, credential operations. Nothing else.
- `users` is the canonical extension point: adding profile fields, organizations, roles-as-data — all happen here.
- Infrastructure features (`email`, `background-jobs`, `file-storage`) follow the same hexagonal pattern as the domain features, so the template teaches one architecture, not two.
- Removing `kanban` does not destroy the worked ReBAC-with-hierarchy reference; it is preserved in an `examples/kanban` branch with a CI job that prevents bitrot.
- Production guardrails are extended: the settings validator refuses `console` email and `in_process` jobs when `APP_ENVIRONMENT=production`.

**Non-Goals:**

- Implementing OAuth/SSO. The credentials split *enables* it, but it is out of scope here.
- A real SpiceDB integration. The adapter stub continues to exist.
- A real S3 adapter. The s3 stub raises `NotImplementedError`, mirroring the SpiceDB pattern.
- Switching to async DB drivers (psycopg → asyncpg). Tracked separately.
- An admin web UI. The API surface is enough for a starter.
- Multi-tenancy primitives (organizations, workspaces). They belong on top of `users`, in consumer projects.

## Decisions

### 1. Three-feature core: `authentication` + `users` + `authorization`

The historical `auth` feature is split. `authentication` keeps everything credential- and session-shaped; `users` owns the `User` entity and its lifecycle.

**Why over keeping a single `auth` feature**: the current `auth` is the only feature that both *implements* and *consumes* authorization ports, which is a smell. Splitting `users` out makes the dependency graph acyclic: `authentication → users`, `users → authorization`, `authorization → users` (via outbound ports). Each feature now has one job.

**Why over absorbing `users` into a generic `accounts` feature**: "users" is an industry-recognized concept (matches Keycloak, Auth0, FusionAuth). Naming it anything else costs more in cognitive load than it saves.

**Alternative considered — keep `users` logic inside `authentication` and just rename the directory**: rejected. The directory is not the problem; the responsibility set is. A rename without a split keeps the cyclic dependency on `authorization` ports.

### 2. Separate `credentials` table from the `users` table

`authentication` owns a new `credentials` table: `(user_id, algorithm, hash, last_changed_at, ...)`. `users` keeps the `User` row (`id`, `email`, `display_name`, `is_active`, `authz_version`, `created_at`, `updated_at`).

**Why**: a `User` can have *zero or many* credentials over its lifetime (password today, passkey tomorrow, OAuth-linked identity the day after). Coupling the hash to the user row makes that impossible without a schema migration. The cost is one extra join on login; the benefit is that adding passkey support later is a new row type, not a table reshape.

**Alternative considered — keep `password_hash` on `users`**: rejected. It encodes the assumption "one user has one password" into the schema. For a starter that aims to be the base of any project, that's a poor default.

**Trade-off**: the registration flow now writes two rows (`users` + `credentials`) inside one transaction. The Unit-of-Work pattern already in place handles this; no new mechanism needed.

### 3. `UserPort` is the only contract between `authentication` and `users`

`users` exposes a single inbound port (`UserPort`) with: `get_by_id`, `get_by_email`, `create`, `update_profile`, `deactivate`. `authentication` calls only through this port. `users` knows nothing about credentials, tokens, or sessions.

**Why**: it mirrors the `AuthorizationPort` pattern already in use and keeps `users` substitutable. A consumer who wants to back `User` with an external identity provider can implement `UserPort` against that provider and `authentication` keeps working unchanged.

**Alternative considered — direct SQLModel import**: rejected on the same grounds Import Linter already enforces for `kanban → auth`. We are not weakening the rules for the core features.

### 4. Outbound ports stay where they are; only their *implementations* move

`authorization`'s outbound ports — `UserRegistrarPort`, `UserAuthzVersionPort`, `AuditPort` — are unchanged. What moves is who implements them:

| Port | Implemented today by | Implemented after |
|---|---|---|
| `UserRegistrarPort` | `authentication` | `users` |
| `UserAuthzVersionPort` | `authentication` | `users` |
| `AuditPort` | `authentication` | `authentication` (no change) |

`AuditPort` stays in `authentication` because the audit log is a security-event store, conceptually closer to sessions than to user profiles. If a second feature needs audit later, the table is promoted to `platform/` (deferred).

### 5. `EmailPort` with `console` + `smtp` adapters; password-reset/email-verify flows are rewired

`email` introduces `EmailPort.send(to, template, context)`. Two adapters ship:

- `console`: logs the rendered email to stdout (JSON), for local dev and tests.
- `smtp`: sends via SMTP. Configured by `APP_EMAIL_SMTP_HOST`, `APP_EMAIL_SMTP_PORT`, `APP_EMAIL_SMTP_USERNAME`, `APP_EMAIL_SMTP_PASSWORD`, `APP_EMAIL_FROM`.

The auth use cases `RequestPasswordReset` and `RequestEmailVerification` stop returning the token in the response. They enqueue a `SendEmailJob` (see decision 6) with the rendered template. `APP_AUTH_RETURN_INTERNAL_TOKENS` survives but is documented as test-only and forbidden in production (already validated).

**Why two adapters and not just one**: a starter that ships only `smtp` forces every new project to set up an SMTP server (or `mailhog`) before running the test suite locally. `console` keeps `make dev` zero-config.

**Alternative considered — a webhook adapter (HTTP POST to an external service)**: deferred. Most consumers will plug `smtp` into a provider like SES, SendGrid, or Resend, which already speak SMTP.

### 6. `JobQueuePort` with `in_process` + `arq` adapters

`background-jobs` introduces `JobQueuePort.enqueue(job_name, payload)`. Two adapters:

- `in_process`: runs the job inline in the current event loop. For dev and tests only — never selected in production (settings validator).
- `arq`: enqueues to Redis; a worker process (`make worker`) consumes the queue.

`arq` is chosen over `dramatiq` and `celery`:

- `arq` is async-native (FastAPI is async; sync workers force an event-loop dance).
- `arq` has only Redis as a dependency. The repo already requires Redis for the distributed rate limiter, so we are not adding new infra — only re-using it.
- `arq` is small (~1500 LOC, single maintainer, but stable and well-suited to "starter" pedagogy).

**Alternative considered — no job queue, do work inline**: rejected. Email sends are slow (SMTP handshake + remote response), and doing them inline turns `POST /auth/password-reset` from a 50ms endpoint into a 2s endpoint. A queue is the right pattern.

**Trade-off**: every consumer now needs Redis to run in production. Already true for the distributed rate limiter; documented in `docs/operations.md`.

### 7. `FileStoragePort` with `local` adapter + `s3` stub

`file-storage` introduces `FileStoragePort.put(key, bytes, content_type)`, `.get(key) -> bytes`, `.delete(key)`, `.signed_url(key, expires_in)`. Two adapters:

- `local`: writes to a path on disk (`APP_STORAGE_LOCAL_PATH`). For dev and tests.
- `s3`: raises `NotImplementedError` from each method, with a docstring pointing at the README on how to fill it in. Mirrors the SpiceDB stub.

**Why a stub for s3 and not a real implementation**: a real S3 adapter needs `boto3` (heavy dependency), bucket configuration, IAM policies, and presigned-URL signing — all of which depend on choices the consumer must make. The stub makes the intended shape explicit without committing to one cloud.

**Why ship `local` at all**: it lets the rest of the starter use `FileStoragePort` (e.g., an attachment endpoint on `_template`) without requiring the consumer to set up a cloud bucket.

### 8. `_template` becomes a live single-resource feature (`things`)

The `_template` scaffold becomes an executable CRUD over a `things` table: `id`, `name`, `owner_id`, `created_at`, `updated_at`. It demonstrates:

- A domain entity with a small invariant (non-empty name).
- A `UnitOfWorkPort` + SQLModel adapter following the existing kanban pattern.
- HTTP routes gated by `require_authorization("read"|"write"|"delete", "thing", id_loader=...)`.
- Wiring into the authorization registry with `owner ⊇ writer ⊇ reader` (no parent walk; flat hierarchy).
- Unit, contract, and e2e tests, plus an integration test with testcontainers.

**Why "things" and not a real noun like "notes" or "items"**: any noun nudges the consumer toward keeping it. `things` signals "this is a placeholder; rename me." The README's first paragraph instructs the rename.

### 9. Kanban is preserved on `examples/kanban` branch, not deleted from history

The `kanban` feature is removed from `main`. The last `main` commit that contains it is tagged `pre-foundation-kanban`. A long-lived branch `examples/kanban` is created from that tag.

CI gains a job that periodically (weekly cron) rebases `examples/kanban` onto `main` and runs `make ci` against the merged tree, catching cases where a platform change breaks the example. If the rebase fails, the job opens an issue.

**Why a branch and not an `examples/` directory in `main`**: keeping it in `main` means `make ci` always runs against it, defeating the goal of making the core small. A branch isolates it.

**Why bother keeping it at all**: the kanban example is the only worked reference of *parent-walk ReBAC* (card → column → board). That pattern is valuable and not obvious from the `_template`. Throwing it away to never reference again is wasteful.

### 10. Settings is split per feature; production validator becomes per-feature

The 160-line monolithic `AppSettings` is decomposed:

- `AuthenticationSettings` (JWT, cookies, password reset/verify token TTLs, rate limit)
- `UsersSettings` (registration policy, default role)
- `AuthorizationSettings` (RBAC flag, principal cache TTL)
- `EmailSettings` (backend, SMTP config)
- `JobsSettings` (backend, Redis URL)
- `StorageSettings` (backend, local path)
- `ObservabilitySettings` (OTEL, metrics)
- `DatabaseSettings` (DSN, pool tuning)
- `ApiSettings` (CORS, trusted hosts, docs, max body size)
- `AppSettings` composes them.

Each sub-setting defines its own `_validate_production` method that `AppSettings._validate_production_settings` calls. Failures aggregate into one error message.

**Why**: today adding a new env var means editing the same 160-line class as everyone else. Per-feature settings let features ship their config alongside their code, matching the rest of the hexagonal layout.

## Risks / Trade-offs

- **Scope is large.** Estimated ~2 weeks of focused work. → Mitigation: implement in the order listed in `tasks.md`, with `make ci` green at each merge. The split-auth precedent (`aea9e82`) is the playbook.
- **Migration of password hashes is the only data migration with no easy rollback.** → Mitigation: a two-phase migration — phase 1 *adds* `credentials` and *copies* hashes; phase 2 (separate release) drops the column. Between phases both columns exist and login reads from both with a preference for `credentials`. A failed rollout reverts to phase 0 without data loss.
- **Adding `arq` makes Redis a hard production dependency.** → Mitigation: it already is for the distributed rate limiter, and the in-process job adapter exists for single-replica / no-Redis dev. The settings validator surfaces this clearly at boot.
- **The `s3` and SpiceDB stubs may rot.** → Mitigation: an Import Linter check enforces that each port has *at least one* working adapter under test; stubs only need to type-check and raise `NotImplementedError` from the documented set of methods. A unit test ensures the stub matches the port's method signatures.
- **`examples/kanban` will lag `main`.** → Mitigation: the weekly rebase CI job is the canary. If it breaks twice in a row, we either fix or delete `examples/kanban`.
- **Per-feature settings means consumers have to look in more places to find a var.** → Mitigation: `docs/operations.md` keeps a flat env-var reference table generated from the per-feature settings classes.
- **The "delete kanban" diff will be enormous (~80 files).** → Mitigation: it lands as the first PR of the change, on its own, before any new feature work. Reviewers see a clean removal, not a removal-tangled-with-additions.

## Migration Plan

The change is delivered as a sequence of PRs. Each PR keeps `make ci` green and is independently revertable. Order matters; do not reorder.

1. **Tag `pre-foundation-kanban`** on current `main`. Create `examples/kanban` branch from the tag.
2. **PR 1 — Remove kanban.** Delete `src/features/kanban/`, its migration, tests, docs, openspec references, CLAUDE.md mentions, README updates. Import Linter contracts for kanban removed. After this PR, `_template` is the only "demo" but still inert.
3. **PR 2 — Bring `_template` to life as `things`.** Create the migration, domain, application, adapters, composition. Wire into authorization registry. Add tests. This gives the developer a working extension point before we move other things around it.
4. **PR 3 — Rename `auth` → `authentication`.** Mechanical rename + import updates + Makefile/test-feature alias. No behavioral change.
5. **PR 4 — Extract `users` (phase 1: code).** Create `src/features/users/`. Move `User` entity, table, registration use case, admin user use cases, and the two outbound-port implementations. `authentication` calls `users.UserPort`. Tests move with the code. No schema changes yet.
6. **PR 5 — Split credentials (phase 1: schema add).** Alembic revision adds `credentials` table and copies existing hashes from `users.password_hash` (still present). Login reads from `credentials`; falls back to `users.password_hash` if missing (handles in-flight rows during deploy).
7. **PR 6 — Split credentials (phase 2: schema drop).** Once production has been on PR 5 for one release cycle, drop `users.password_hash`. Fallback code removed.
8. **PR 7 — Add `email` feature.** `EmailPort`, `console` + `smtp` adapters, settings, templates. `RequestPasswordReset` and `RequestEmailVerification` rewired to call `EmailPort` (synchronously for now).
9. **PR 8 — Add `background-jobs` feature.** `JobQueuePort`, `in_process` + `arq` adapters, settings, `make worker` target. The `SendEmailJob` is added and the auth flows enqueue it instead of calling `EmailPort` directly.
10. **PR 9 — Add `file-storage` feature.** `FileStoragePort`, `local` adapter, `s3` stub. No consumer yet. Optional: `_template/things` gains an `/attachments` sub-route demonstrating uploads.
11. **PR 10 — Split `AppSettings` per feature.** Mechanical refactor; the validator aggregates errors as before.
12. **PR 11 — Docs + README + CLAUDE.md rewrite.** Reframe around "clone, rename, run." Coverage gate bumped from 70% to 80%.

Rollback strategy: each PR is independently revertable. PRs 5 and 6 (credentials split) are the only ones with data migrations; PR 5's migration is reversible (the `password_hash` column is preserved). PR 6's drop is the point of no return — gate it behind a one-release soak period.

## Open Questions

- **Email templates: where do they live?** Two options: under `email/templates/` (engine-agnostic, simple Jinja2 strings) or inside each feature that sends them (e.g., `authentication/email_templates/`). Locality argues for the latter; cohesion of the `email` feature argues for the former. Lean: per-feature templates, registered with `email` at startup the way features register with the authorization registry.
- **Should `users` own login attempts and lockout?** Lockout state is user-shaped, but the trigger is authentication-shaped. Lean: a `LockoutPort` on `users` that `authentication` calls after N failed attempts. Defer until needed.
- **Do we need a `notifications` feature on top of `email`?** A consumer who wants in-app notifications + email needs a higher-level abstraction. Out of scope here; flagged for a follow-up change.
- **Audit log promotion to `platform/`?** Deferred — wait for a second feature to need audit before promoting. Until then `authentication` owns it.
- **`arq` version pinning.** `arq` has had occasional breaking changes. Lean: pin to a minor range (`~=0.26`) and add a smoke test in CI that exercises enqueue → worker → completion.
