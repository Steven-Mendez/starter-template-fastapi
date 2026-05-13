## Context

GDPR Art. 17 grants the **data subject** the right to erasure ("right to be forgotten"). Art. 15 grants the symmetric right of access. Both rights belong to the user themselves; restricting them to admin-only would non-comply. The implementation is "scrub PII while keeping enough to preserve referential integrity and audit trail".

## Decisions

- **Self-erase = YES.** GDPR Art. 17 applies to data subjects. `DELETE /me/erase` is required. Admin-only erasure is also supported for operator workflows (e.g., responding to mailed legal requests).
- **Re-auth on `DELETE /me/erase`.** The endpoint requires the user's current password in the body — protects against a stolen session token erasing the account. (If the user has no password, e.g., SSO-only, the endpoint requires a fresh access token issued within the last 5 minutes.)
- **Erasure is async (`202 Accepted` + job id).** The transaction touches multiple tables and may call `FileStoragePort.delete` for many blobs; doing it synchronously risks request-timeout. The HTTP response shape is:
  ```json
  {"status": "accepted", "job_id": "...", "estimated_completion_seconds": 60}
  ```
  with `Location: /me/erase/status/<job_id>` (status endpoint is out of scope for this proposal; clients should accept "no body, you'll get notified" semantics).
- **Export is synchronous + signed URL.** Export writes a JSON blob to `FileStoragePort` and returns `{"download_url": "<signed>", "expires_at": "<ts>"}`. Signed URL TTL: 15 minutes. Rationale: the blob is typically small, and the signed-URL pattern decouples the HTTP response from blob size. If the synchronous path proves slow (>500ms p95), swap to a job + a status endpoint; the response shape (`download_url`) stays the same.
- **Scrub-in-place over hard-delete.** Preserves audit-log row counts and referential integrity from FKs. PII fields are nulled/replaced; the row stays. The `is_erased` flag is the authoritative signal.
- **`erased+<uuid>@erased.invalid` instead of `NULL` email.** Keeps the unique-on-email constraint trivially satisfied without `WHERE is_erased=false` partial indexes.
- **`UserPort.get_by_email` filters out `is_erased=true`.** A re-registration with the original email gets a fresh user row.
- **PII column inventory in `docs/operations.md`.** Every developer adding a column to a user-adjacent table updates this list. Linked from `CLAUDE.md`.

## Non-goals

- **Not a full data-portability product.** The export is a single JSON blob covering the in-scope tables; it is not a Google-Takeout-style multi-format archive, does not include rendered HTML/PDF reports, and does not stream large objects out-of-band.
- **Not third-party data erasure.** This change scrubs PII in this service's own database and blob store. It does NOT propagate erasure to downstream processors (analytics, mail providers, SaaS integrations); operators are responsible for kicking off those workflows out-of-band.
- **Not regulator-grade audit logging.** The `user.erased` event is a service-level audit row, not a tamper-evident WORM ledger. A future change can promote the audit log to an append-only store if compliance requires it.
- **Not a status / progress endpoint for the erasure job.** The 202 response carries a `Location` header by convention, but the status endpoint itself is out of scope; clients accept "no body, you'll get notified" semantics.
- **Not a real-time consent management surface.** Consent capture, cookie banners, and lawful-basis tracking are separate from the data-subject-rights endpoints landed here.

## Risks / Trade-offs

- **Risk**: legal requires hard-delete with no row stub. Mitigation: `EraseUser` is one place; flip the implementation to `DELETE FROM users WHERE id = ?` if needed. The scrub-in-place is a documented default.
- **Risk**: forgetting a PII-bearing column when a new feature adds one. Mitigation: PII column inventory in `docs/operations.md` + a test that asserts post-erasure no PII strings remain in any user-referencing table.
- **Risk**: the async job fails between `users` scrub and `file_storage` purge. Mitigation: the `erase_user` job is idempotent — re-running it on an already-erased user is a no-op on `users` and a best-effort `delete` on file storage.

## Migration

One PR for the code + the `is_erased` column migration (reversible). The job handler must be registered in both `src/main.py` (for in-process backend) and `src/worker.py` (for arq) per the project convention.
