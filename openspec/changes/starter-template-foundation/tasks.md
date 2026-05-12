## 1. Preparation

- [ ] 1.1 Tag current `main` as `pre-foundation-kanban` and create branch `examples/kanban` from the tag
- [ ] 1.2 Add a weekly CI workflow that rebases `examples/kanban` onto `main` and runs `make ci` against the merged tree; opens an issue if the rebase or `make ci` fails
- [ ] 1.3 Confirm `make ci` is green on `main` before starting any removal

## 2. Remove kanban (PR 1)

- [ ] 2.1 Delete `src/features/kanban/` entirely (production code, tests, fakes, contracts)
- [ ] 2.2 Drop the kanban Alembic migration; create a follow-up migration that drops `boards`, `columns_`, and `cards` tables
- [ ] 2.3 Remove kanban references from `src/main.py` (imports, route mounts, container build)
- [ ] 2.4 Remove the `kanban → auth` and `kanban`-specific Import Linter contracts from `pyproject.toml`
- [ ] 2.5 Remove kanban references from `CLAUDE.md`, `README.md`, `docs/api.md`, `docs/user-guide.md`, `docs/architecture.md`
- [ ] 2.6 Archive any kanban-specific entries in `openspec/specs/` if present, and update `openspec` listings
- [ ] 2.7 Run `make ci` and confirm green; resolve any dangling references

## 3. Bring `_template` to life as `things` (PR 2)

- [ ] 3.1 Create `things` SQLModel table (`id`, `name`, `owner_id`, `created_at`, `updated_at`) under `src/features/_template/adapters/outbound/persistence/sqlmodel/models.py`
- [ ] 3.2 Generate an Alembic revision for the new table
- [ ] 3.3 Implement the `Thing` domain entity with the non-empty-name invariant
- [ ] 3.4 Implement `UnitOfWorkPort`, `ThingRepositoryPort`, and the SQLModel adapter
- [ ] 3.5 Implement use cases: `CreateThing`, `GetThing`, `ListThings`, `UpdateThing`, `DeleteThing`, each returning `Result[T, ApplicationError]`
- [ ] 3.6 Implement HTTP routes (`POST/GET/PATCH/DELETE /things`, `GET /things`) gated by `require_authorization`
- [ ] 3.7 Wire into the authorization registry: `thing` resource type with `owner ⊇ writer ⊇ reader`; `CreateThing` writes the `owner` tuple in the same unit of work
- [ ] 3.8 Add unit tests (domain, use cases) and e2e tests (HTTP); add contract tests for the repository port
- [ ] 3.9 Add a testcontainers integration test exercising the SQLModel adapter against real PostgreSQL
- [ ] 3.10 Update `docs/feature-template.md` to describe the new `things` example and the "copy and rename" workflow

## 4. Rename `auth` to `authentication` (PR 3)

- [ ] 4.1 Rename directory `src/features/auth/` → `src/features/authentication/`
- [ ] 4.2 Update all imports across the codebase (including tests, fakes, contracts, conftest.py files)
- [ ] 4.3 Update `Makefile` `test-feature` to accept both `auth` (alias, prints deprecation) and `authentication`
- [ ] 4.4 Update `pyproject.toml` Import Linter contract names referencing `auth` → `authentication`
- [ ] 4.5 Update env-var documentation references from "auth feature" to "authentication feature"; env-var names themselves stay `APP_AUTH_*` for backwards compatibility
- [ ] 4.6 Update `CLAUDE.md` and `docs/` references
- [ ] 4.7 Run `make ci` and confirm green

## 5. Extract `users` feature — code move (PR 4)

- [ ] 5.1 Scaffold `src/features/users/` mirroring `_template` layout: domain, application, adapters, composition, tests
- [ ] 5.2 Move `UserTable` SQLModel definition from `authentication` to `users/adapters/outbound/persistence/sqlmodel/models.py`
- [ ] 5.3 Define `UserPort` Protocol in `users/application/ports/user_port.py` with `get_by_id`, `get_by_email`, `create`, `update_profile`, `deactivate`
- [ ] 5.4 Implement `SQLModelUserRepository` (and its session-scoped variant) under `users/adapters/outbound/persistence/sqlmodel/`
- [ ] 5.5 Move user-related use cases from `authentication` to `users`: `RegisterUser` (split: user creation now lives here, credential write stays in authentication), `GetUserById`, `GetUserByEmail`, `UpdateProfile`, `DeactivateUser`
- [ ] 5.6 Move admin user use case `ListUsers` to `users`
- [ ] 5.7 Move `SQLModelUserRegistrarAdapter` (implements `UserRegistrarPort`) from `authentication` to `users/adapters/outbound/user_registrar/`
- [ ] 5.8 Move `SQLModelUserAuthzVersionAdapter` (and session-scoped variant) from `authentication` to `users/adapters/outbound/authz_version/`
- [ ] 5.9 Mount user routes (`GET /me`, `PATCH /me`, `DELETE /me`, `GET /admin/users`) from `users/adapters/inbound/http/`
- [ ] 5.10 Update `authentication`'s use cases to take a `UserPort` dependency instead of importing `UserTable`
- [ ] 5.11 Update `main.py` composition: build the `users` container before `authorization`; pass `users.user_authz_version_adapter` and `users.user_registrar_adapter` into `build_authorization_container`
- [ ] 5.12 Add Import Linter contracts: `users ↛ authentication`, `authentication ↛ users (adapters)`, `users ↛ authorization (adapters)`
- [ ] 5.13 Move user-related tests (unit, e2e, integration, contracts) from `authentication` to `users`
- [ ] 5.14 Run `make ci`; expect tests around registration/admin-users to need fixture updates — fix until green

## 6. Split credentials (PR 5 — schema add)

- [ ] 6.1 Create `credentials` SQLModel table in `authentication/adapters/outbound/persistence/sqlmodel/models.py` with columns `user_id`, `algorithm`, `hash`, `last_changed_at`, `created_at` and a unique constraint on `(user_id, algorithm)`
- [ ] 6.2 Generate an Alembic revision that creates the table and copies existing `users.password_hash` into `credentials` with `algorithm='argon2'`
- [ ] 6.3 Add a `CredentialRepositoryPort` and SQLModel adapter under `authentication`
- [ ] 6.4 Update `LoginUser` to read from `credentials` first; fall back to `users.password_hash` if no credential row exists for the user (log `auth.credentials.fallback_used`)
- [ ] 6.5 Update `RegisterUser` to write to `credentials` (and stop writing `users.password_hash` for new users)
- [ ] 6.6 Update `ConfirmPasswordReset` to update the `credentials` row
- [ ] 6.7 Add unit + contract tests for the credentials repository; add an e2e test asserting login still works with a user whose hash exists only in `users.password_hash` (fallback path)
- [ ] 6.8 Run `make ci`; confirm migrations apply cleanly on a copy of a populated dev database

## 7. Split credentials (PR 6 — schema drop)

- [ ] 7.1 Add an Alembic revision that drops `users.password_hash`
- [ ] 7.2 Remove the fallback read path from `LoginUser`; remove the `auth.credentials.fallback_used` log line
- [ ] 7.3 Update `UserTable` model definition (drop the column)
- [ ] 7.4 Update `UserPort.create` to no longer accept a `password_hash` argument; the password flow goes through `authentication`'s `CredentialRepositoryPort`
- [ ] 7.5 Run `make ci`; confirm round-trip migration (`alembic downgrade -1 && alembic upgrade head`) preserves schema
- [ ] 7.6 Document in `docs/operations.md` that PR 6 should only be deployed after PR 5 has been in production for at least one release cycle

## 8. Add `email` feature (PR 7)

- [ ] 8.1 Scaffold `src/features/email/` mirroring `_template` layout
- [ ] 8.2 Define `EmailPort` Protocol with `send(to, template_name, context) -> Result[None, EmailError]`
- [ ] 8.3 Implement `ConsoleEmailAdapter` that logs the rendered email at `INFO` with structured fields
- [ ] 8.4 Implement `SmtpEmailAdapter` using `smtplib`, with TLS support and proper exception mapping
- [ ] 8.5 Implement `EmailTemplateRegistry` (mirrors `AuthorizationRegistry`): features call `register_template(name, path)` at composition; sealed in `main.py`
- [ ] 8.6 Add Jinja2 as a dependency; implement template rendering with a small context schema per template
- [ ] 8.7 Add `EmailSettings` (backend, SMTP host/port/username/password/from) under `src/features/email/composition/settings.py`
- [ ] 8.8 Wire `EmailContainer` in `main.py`; add the production validator clause refusing `console` when `APP_ENVIRONMENT=production`
- [ ] 8.9 Move authentication's email templates under `src/features/authentication/email_templates/`; authentication registers them at startup
- [ ] 8.10 Rewire `RequestPasswordReset` and `RequestEmailVerification` to render via the template registry and call `EmailPort.send(...)` (synchronously for now — the queue swap happens in the next PR)
- [ ] 8.11 Update `APP_AUTH_RETURN_INTERNAL_TOKENS` documentation and add a production-validator clause that refuses `true` in production
- [ ] 8.12 Add unit tests (template rendering, adapter behavior with a fake SMTP server using `aiosmtpd`), contract tests (both adapters pass the same suite), and e2e tests asserting password-reset returns 202 with no token in the body
- [ ] 8.13 Run `make ci`

## 9. Add `background-jobs` feature (PR 8)

- [ ] 9.1 Scaffold `src/features/background_jobs/`
- [ ] 9.2 Add `arq` as a dependency, pinned to `~=0.26`
- [ ] 9.3 Define `JobQueuePort` Protocol with `enqueue(job_name, payload)` and `enqueue_at(job_name, payload, run_at)`
- [ ] 9.4 Implement `InProcessJobQueueAdapter` (synchronous; runs handlers inline)
- [ ] 9.5 Implement `ArqJobQueueAdapter` using `arq`, backed by Redis
- [ ] 9.6 Implement `JobHandlerRegistry`: features call `register_handler(job_name, handler)` at composition; sealed in `main.py`
- [ ] 9.7 Create the worker entrypoint `src/worker.py` that loads the same composition root and starts `arq.worker.run_worker`
- [ ] 9.8 Add `make worker` target invoking the worker entrypoint
- [ ] 9.9 Implement `SendEmailJob` in `email` feature: a handler registered as `send_email` that consumes a payload `{to, template_name, context}` and calls the wired `EmailPort` adapter
- [ ] 9.10 Update `RequestPasswordReset` and `RequestEmailVerification` to enqueue `send_email` via `JobQueuePort` instead of calling `EmailPort.send` directly
- [ ] 9.11 Add `JobsSettings` (backend, Redis URL); production validator refuses `in_process` when `APP_ENVIRONMENT=production`
- [ ] 9.12 Add unit tests, contract tests, and a docker-backed integration test exercising enqueue → arq worker → handler invocation
- [ ] 9.13 Document in `docs/operations.md` that a worker process must be running in production
- [ ] 9.14 Run `make ci`

## 10. Add `file-storage` feature (PR 9)

- [ ] 10.1 Scaffold `src/features/file_storage/`
- [ ] 10.2 Define `FileStoragePort` Protocol with `put`, `get`, `delete`, `signed_url`
- [ ] 10.3 Implement `LocalFileStorageAdapter` that writes under `APP_STORAGE_LOCAL_PATH`; key derivation uses sha256 prefix dirs to avoid pathological directory sizes
- [ ] 10.4 Implement `S3FileStorageAdapter` stub raising `NotImplementedError` from each method; include a `README.md` under the adapter directory describing the boto3 mapping and IAM requirements
- [ ] 10.5 Add `StorageSettings` (backend, local path); production validator refuses `local` when `APP_ENVIRONMENT=production` *only if* a consumer feature has wired it
- [ ] 10.6 Add fake adapter under `src/features/file_storage/tests/fakes/`
- [ ] 10.7 Add contract tests that run against the fake, the local adapter, and (skipped) the s3 stub
- [ ] 10.8 Optional: add `POST /things/{id}/attachments` to `_template` demonstrating an upload, gated by `require_authorization("update", "thing", id_loader=...)`
- [ ] 10.9 Run `make ci`

## 11. Split settings per feature (PR 10)

- [ ] 11.1 Create per-feature settings classes under each feature's `composition/settings.py`: `AuthenticationSettings`, `UsersSettings`, `AuthorizationSettings`, `EmailSettings`, `JobsSettings`, `StorageSettings`
- [ ] 11.2 Create platform-level settings classes: `DatabaseSettings`, `ApiSettings`, `ObservabilitySettings`
- [ ] 11.3 Rewrite `src/platform/config/settings.py` `AppSettings` to compose the sub-settings, exposing them as attributes
- [ ] 11.4 Move each `_validate_production_*` clause to its owning sub-settings class; `AppSettings._validate_production_settings` aggregates errors from each
- [ ] 11.5 Update every consumer that reads `settings.<flat_attr>`; ensure backwards-compat property accessors exist for the duration of this PR (and remove in a follow-up if desired)
- [ ] 11.6 Generate the env-var reference table in `docs/operations.md` from the per-feature settings classes
- [ ] 11.7 Run `make ci`

## 12. Documentation, CI, and polish (PR 11)

- [ ] 12.1 Rewrite `README.md` around "clone, rename `_template`, run" — `_template` is the starting point, the four feature directories are infrastructure ready to use
- [ ] 12.2 Rewrite `docs/architecture.md` to describe the new feature inventory (authentication, users, authorization, email, background_jobs, file_storage, _template) and the dependency graph
- [ ] 12.3 Update `CLAUDE.md` to match: new feature list, new env vars, new "adding a feature" steps
- [ ] 12.4 Add `docs/email.md`, `docs/background-jobs.md`, `docs/file-storage.md` describing each feature's configuration and how to extend it
- [ ] 12.5 Bump coverage gate in `pyproject.toml` from 70% to 80%
- [ ] 12.6 Add an Import Linter contract that asserts every outbound port has at least one adapter registered as the "test default" (catches stubs that drift from the port signature)
- [ ] 12.7 Run `make ci`; resolve any coverage shortfalls
- [ ] 12.8 Tag the resulting commit as `v0.2.0-starter-foundation`; update `README.md` with a "what's new" note pointing at this change's archive

## 13. Archive the change

- [ ] 13.1 Once all PRs are merged and deployed to a reference environment, run `openspec archive starter-template-foundation`
- [ ] 13.2 Verify that the archived `openspec/specs/` reflects the new state (users, email, background-jobs, file-storage specs present; authentication and authorization specs updated with deltas applied)
- [ ] 13.3 Update purpose lines in any spec files still marked `TBD - created by archiving change ...`
