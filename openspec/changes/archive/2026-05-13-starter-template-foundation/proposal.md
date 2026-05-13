## Why

The repository is sold as a *starter template* but behaves as a *reference architecture*. To bootstrap a new project today, the developer has to delete the entire `kanban` feature (~80 files, its migration, tests, routes, docs) and then build the infrastructure every real backend needs — user management beyond credentials, transactional email, background jobs, file storage — from scratch. That is not "clone and tweak"; it is "clone, gut, and rebuild the same scaffolding I keep rebuilding."

This change converts the repo into a true starter: it removes the domain-specific example, extracts user management into its own feature so `authentication` can be small and focused, and lands the four cross-cutting capabilities (`users`, `email`, `background-jobs`, `file-storage`) that every consumer will otherwise have to add by hand on day one.

## What Changes

- **BREAKING** Remove the `kanban` feature entirely: `src/features/kanban/`, its Alembic migration, HTTP routes, docs, openspec references, and CLAUDE.md mentions. Preserve it on a separate `examples/kanban` branch for users who want a worked ReBAC-with-hierarchy reference.
- **BREAKING** Extract a new `users` feature from `auth`. The `User` entity, its table, registration, admin user listing/CRUD, and the adapters that today implement `UserRegistrarPort` and `UserAuthzVersionPort` move into `src/features/users/`. `authentication` keeps tokens, login/logout, refresh, password reset, email verification, rate limiting, and principal resolution — and depends on a new `UserPort` exposed by `users`.
- **BREAKING** Split credentials from the user record: introduce a `credentials` table owned by `authentication` (password hash, algorithm, last-changed timestamp). The `users` table keeps profile fields, status, and `authz_version`. This opens the door to OAuth/passkeys without touching `users`.
- Add an `email` feature: an `EmailPort` plus two adapters — `console` (logs the email body for local dev and tests) and `smtp` (production-ready). Auth's password-reset and email-verify flows are rewired to call `EmailPort` instead of returning the token in the response. `APP_AUTH_RETURN_INTERNAL_TOKENS` is kept only for the e2e test path and is documented as test-only.
- Add a `background-jobs` feature: a `JobQueuePort` plus an in-process adapter (for dev/test) and an `arq`-backed adapter (for production, Redis-backed). One reference job (`SendEmailJob`) demonstrates the pattern by being the default delivery channel for `email`.
- Add a `file-storage` feature: a `FileStoragePort` plus a `local-filesystem` adapter and an `s3` adapter stub. No feature consumes it yet; it ships as scaffolding ready for the user to wire in. (Mirrors how the SpiceDB adapter ships as a stub today.)
- Bring `src/features/_template` to life: it becomes an executable single-resource CRUD (`things`) wired into authorization (owner ⊇ writer ⊇ reader), with a real migration, tests, and routes. The user's first move on a new project is `cp -r features/_template features/<their-feature>`.
- Update Import Linter contracts to enforce the new boundaries (`auth` ↛ `users` direct table access, `users` ↛ `authentication`, no feature imports `email`/`jobs`/`storage` adapters directly).
- Update `README.md`, `docs/`, and `CLAUDE.md` to describe the new feature inventory and the "what do I do first" workflow for a fresh clone.

## Capabilities

### New Capabilities

- `users`: ownership of the `User` entity, its table, its lifecycle (registration, profile read/update, deactivation), and admin user listing/management. Implements the outbound ports authorization defines for user-shaped state.
- `email`: the `EmailPort` contract, the `console` and `smtp` adapters, and the rendering of templated transactional emails (password reset, email verification).
- `background-jobs`: the `JobQueuePort` contract, the in-process adapter for dev/test, the `arq` adapter for production, and a worker entrypoint (`make worker`).
- `file-storage`: the `FileStoragePort` contract, the local-filesystem adapter, and the s3 adapter stub.

### Modified Capabilities

- `authentication`: loses the `User` entity, registration's user-creation responsibility, admin user endpoints, and the implementations of `UserRegistrarPort` / `UserAuthzVersionPort`. Gains a separate `credentials` table and a `UserPort` dependency on `users`. Password-reset and email-verify use cases call `EmailPort` instead of returning tokens in the response.
- `authorization`: outbound ports (`UserRegistrarPort`, `UserAuthzVersionPort`, `AuditPort`) move their *implementations* from `auth` to `users` (and, for `AuditPort`, stay in `authentication` as the audit log is a security-event concern). No change to the port contracts themselves.

## Impact

- **Removed**: `src/features/kanban/` (entire feature), `alembic/versions/<kanban migration>`, `src/features/kanban/tests/`, kanban references in `docs/`, `README.md`, `CLAUDE.md`, and `openspec/specs/`. Preserved on `examples/kanban` branch.
- **Renamed**: `src/features/auth/` → `src/features/authentication/`. The directory rename clarifies that the feature owns *authentication*, not *the user*. All imports, `make test-feature FEATURE=auth`, and docs update accordingly.
- **New code**: `src/features/users/`, `src/features/email/`, `src/features/background_jobs/`, `src/features/file_storage/`, all mirroring the `_template` layout.
- **New tables**: `users.credentials` (owned by `authentication`). Existing `users` table loses `password_hash` (moved) and stays as the canonical user record.
- **Migrations**: one Alembic revision per new/changed table; the `credentials` extraction is a data migration (copy existing hashes, then drop the column).
- **New dependencies**: `arq` (background jobs). `boto3` is *not* added; the s3 adapter stub raises `NotImplementedError` until a consumer needs it (same pattern as the SpiceDB stub).
- **New env vars**: `APP_EMAIL_BACKEND` (`console`|`smtp`), `APP_EMAIL_SMTP_*`, `APP_JOBS_BACKEND` (`in_process`|`arq`), `APP_JOBS_REDIS_URL`, `APP_STORAGE_BACKEND` (`local`|`s3`), `APP_STORAGE_LOCAL_PATH`. Production validator extended to refuse `console` email and `in_process` jobs when `APP_ENVIRONMENT=production`.
- **CI**: `make ci` gains an `examples/kanban` smoke-build job to prevent the kept reference from rotting; Import Linter contracts updated; coverage gate raised from 70% to 80% now that there is less ad-hoc domain code to dilute it.
- **Docs**: `README.md` reframed around "clone, rename, run" with `_template` as the starting point; `docs/feature-template.md` becomes the canonical "add a feature" guide; new pages for `email`, `background-jobs`, `file-storage`.
- **Operational**: deployments now need Redis (for `arq` jobs) in addition to PostgreSQL. This is called out in `docs/operations.md` and in the production validator.
