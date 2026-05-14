## ADDED Requirements

### Requirement: GDPR erasure (Art. 17) and access (Art. 15) endpoints

The project SHALL provide an `EraseUser` use case that, in one transaction, scrubs PII from `users` (email replaced with `erased+<uuid>@erased.invalid`, `last_login_at` nulled, `authz_version` bumped, `is_active=false`, `is_erased=true`; `is_verified` is preserved as a non-PII state fact), removes the PII keys (`ip_address`, `user_agent`, `family_id`) from `auth_audit_events.event_metadata` for that user, deletes `credentials`/`refresh_tokens`/`auth_internal_tokens`, enqueues a `delete_user_assets` outbox row (handled by the worker, not inline), and records a `user.erased` audit event with payload `{user_id, reason}`. Erasure SHALL be triggered via `JobQueuePort` (deferred) and the HTTP endpoint SHALL return `202 Accepted` with a job id.

(Note: as the `users` table grows new PII columns, the scrub list MUST grow alongside it; the PII column inventory in `docs/operations.md` is the canonical reference.)

The project SHALL provide both a self-service erasure route (`DELETE /me/erase`, requiring re-auth) and an admin route (`POST /admin/users/{user_id}/erase`, gated by `system:main#admin`).

The project SHALL provide an `ExportUserData` use case and corresponding routes (`GET /me/export` and `GET /admin/users/{user_id}/export`) that return a JSON `{download_url, expires_at}` body where `download_url` is a `FileStoragePort` signed URL (TTL 15 minutes) for a JSON blob containing the user's row, profile, audit events, and file metadata.

#### Scenario: Self-erase requires re-auth

- **GIVEN** an authenticated user with a password credential
- **WHEN** the user calls `DELETE /me/erase` with the correct password in the body
- **THEN** the response is `202 Accepted` with `{status: "accepted", job_id: ..., estimated_completion_seconds: ...}`
- **AND** the `erase_user` job is enqueued for `user_id`

#### Scenario: Self-erase with wrong password is rejected

- **WHEN** the user calls `DELETE /me/erase` with an incorrect password
- **THEN** the response is `401 Unauthorized`
- **AND** no erasure job is enqueued

#### Scenario: Admin erasure path

- **GIVEN** an admin holding `admin` on `system:main`
- **WHEN** the admin calls `POST /admin/users/{user_id}/erase`
- **THEN** the response is `202 Accepted` and the `erase_user` job is enqueued for `user_id`

#### Scenario: Non-admin cannot erase another user

- **WHEN** a non-admin user calls `POST /admin/users/{other_id}/erase`
- **THEN** the response is `403 Forbidden`
- **AND** no job is enqueued

#### Scenario: Erased user's email is no longer matchable

- **GIVEN** an erased user (`is_erased=true`)
- **WHEN** any caller invokes `UserPort.get_by_email("original@example.com")`
- **THEN** the result is `None`
- **AND** a fresh registration with the original email succeeds and produces a new `user_id`

#### Scenario: Audit-log row survives erasure, scrubbed

- **GIVEN** an audit event `auth.login.succeeded` for the user with `event_metadata.ip_address = "1.2.3.4"`
- **WHEN** the user is erased
- **THEN** the audit row still exists
- **AND** `event_metadata.ip_address`, `event_metadata.user_agent`, and `event_metadata.family_id` are absent
- **AND** the row's `user_id` still references the scrubbed `users` row

#### Scenario: Erasure is idempotent

- **GIVEN** a user that has already been erased
- **WHEN** the `erase_user` job runs again for the same `user_id`
- **THEN** the job completes without raising
- **AND** the row state is unchanged

#### Scenario: Export endpoint returns a signed URL

- **GIVEN** an authenticated user with profile data and audit events
- **WHEN** the client calls `GET /me/export`
- **THEN** the response is `200 OK` with `{download_url: str, expires_at: datetime}`
- **AND** fetching `download_url` within `expires_at` returns a JSON document containing the user row, profile fields, the user's audit events, and the user's file-storage metadata

#### Scenario: Export when the user has no associated data

- **GIVEN** a freshly registered user with no audit events, no file uploads, and no profile fields beyond the registration row
- **WHEN** the user calls `GET /me/export`
- **THEN** the response is `200 OK` with `{download_url, expires_at}`
- **AND** the JSON document at `download_url` contains the user row and empty arrays / objects for the per-section keys (`audit_events: []`, `files: []`, `profile: {…}` with the registration-time values)
- **AND** the response shape is identical to the "has data" case — clients do not need to special-case the empty user

#### Scenario: Erasure when the assets-cleanup port fails

- **GIVEN** a user with file-storage assets and a `UserAssetsCleanupPort` adapter whose `delete_user_assets` call raises a transient error
- **WHEN** the `erase_user` job runs
- **THEN** the database scrub still commits (`is_erased=true`, PII columns cleared, audit metadata scrubbed, credentials/refresh-token rows deleted)
- **AND** the asset-cleanup step is retried via the existing outbox/worker backoff (the cleanup runs as a separate `delete_user_assets` outbox row, not inline)
- **AND** the user-facing `user.erased` audit event has already been recorded — re-running the cleanup is idempotent and does not duplicate that event
