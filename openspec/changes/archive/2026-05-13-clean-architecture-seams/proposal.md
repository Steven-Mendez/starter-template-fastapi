## Why

Three architecture-seam issues that the Import Linter contracts let through on a technicality but that contradict the spirit of the layering rules:

1. **`application` layer imports another feature's `composition` package.** `request_password_reset.py:20` and `request_email_verification.py:20` import `features.email.composition.jobs.SEND_EMAIL_JOB`. Composition is the outermost ring; application is supposed to depend only on its own domain + application. The existing import-linter contracts forbid only `email.adapters`, so the rule is honored to the letter and broken in spirit. The job-name constant is a pure-data fact about the email feature's contract; it has no business living in the composition layer.
2. **`OutboxPort` wiring leaks `sqlmodel.Session` into every producer's composition root and forces a post-hoc registration hack on the auth repository.** `features/outbox/composition/container.py:38` declares `SessionScopedOutboxFactory = Callable[[Session], OutboxPort]`. Producer composition (`features/authentication/composition/container.py:70,111`) imports that alias so its `build_auth_container(...)` parameter list mentions `Session` transitively. Worse, the auth repository exposes `set_outbox_session_factory(factory)` (`adapters/outbound/persistence/sqlmodel/repository.py:359-370`) — a post-hoc registration that the docstring itself flags as a workaround ("the existing constructor signature is part of the migration test suite — adding it inline would force a wider rewrite than this change needs"). A future Mongo-backed outbox can satisfy `OutboxPort` but cannot satisfy a port that traffics `sqlmodel.Session`. (Use-case code already calls `tx.outbox.enqueue(...)` cleanly — the leak is in the wiring + the registration hack, not in application code.)
3. **`management.py` is a second composition root inside the `authentication` feature.** `src/features/authentication/management.py` reaches across every other feature's composition (`authorization`, `background_jobs`, `email`, `outbox`, `users`) to assemble a parallel application for the bootstrap CLI. Per CLAUDE.md, composition belongs in `main.py` / `worker.py` / per-feature `composition/`. This duplicates `main.py`'s wiring (drift risk), and the current implementation also never seals the `AuthorizationRegistry` before invoking `BootstrapSystemAdmin` — fixed on the way by this change. Turns `authentication` into a composition god-module masquerading as a feature.

None of these is a runtime defect today. They are gradual-decay seams: each one slightly weakens the boundary, and the next contributor that needs to do something similar copies the precedent.

## What Changes

- Move the `SEND_EMAIL_JOB` constant (and any other purely-application-layer email facts) from `features/email/composition/jobs.py` to `features/email/application/jobs.py` (new module). The composition module continues to host `register_send_email_handler(...)` (legitimately composition). Update both callers in `authentication.application`. Add a broad Import Linter contract: every `features.*.application` MUST NOT import `features.*.composition` (covers this case and prevents the next one).
- Replace the `Callable[[Session], OutboxPort]` factory shape with a port-level seam that doesn't traffic in SQLModel types. Concretely: declare `OutboxUnitOfWorkPort` in `outbox.application.ports` with a `transaction()` context manager that yields an `OutboxWriter`. Producers' composition takes the port. The SQLModel adapter implements it bound to its own `sessionmaker`, removing the post-hoc `set_outbox_session_factory(...)` registration on the auth repository.
- Relocate `src/features/authentication/management.py` to `src/cli/create_super_admin.py`. Wiring still uses each feature's `composition/container.py` API; the difference is the CLI lives in a project-level composition root, not inside a feature. Seal the `AuthorizationRegistry` before invoking `BootstrapSystemAdmin` (current behavior misses this).

**Capabilities — Modified**
- `project-layout`: tightens the layer rules and clarifies where composition roots can live.

**Capabilities — New**
- None.

## Depends on

- None. This change establishes the seams others build on.

## Conflicts with

This change MUST land first in the architecture/lifecycle cluster. The following downstream changes touch the same files and MUST rebase onto this one after it merges:

- `fix-bootstrap-admin-escalation` — also edits `src/features/authentication/management.py`. After this change lands, that file no longer exists; the downstream change must apply its new flag wiring inside `src/cli/create_super_admin.py` instead.
- `make-auth-flows-transactional` — also edits `src/features/authentication/composition/container.py`. After this change lands, the producer wiring takes `OutboxUnitOfWorkPort` instead of `Callable[[Session], OutboxPort]`; the downstream change must extend that port-based wiring rather than the deleted factory shape.

## Impact

- **Code (new)**: `src/features/email/application/jobs.py`, `src/features/outbox/application/ports/outbox_uow_port.py`, `src/cli/__init__.py`, `src/cli/create_super_admin.py`.
- **Code (modified)**: `src/features/email/composition/jobs.py` (imports `SEND_EMAIL_JOB` from application), `src/features/authentication/application/use_cases/auth/request_password_reset.py`, `src/features/authentication/application/use_cases/auth/request_email_verification.py`, `src/features/outbox/composition/container.py` (drop `SessionScopedOutboxFactory`), `src/features/outbox/adapters/outbound/sqlmodel/repository.py` (implement new port), `src/features/authentication/composition/container.py` (consume `OutboxUnitOfWorkPort`), `src/main.py` (wire the new port), `pyproject.toml` (Import Linter contracts; CLI script entry point if any), `docs/outbox.md`, `docs/operations.md`.
- **Code (deleted)**: `src/features/authentication/management.py`.
- **Import Linter**: tighten `authentication.application ↛ email.composition`; add `outbox.application ↛ sqlmodel`; add `features.* ↛ src.cli`.
- **Migrations**: none.
- **Production**: no behavior change; this is a refactor.
- **Tests**: existing tests should continue to pass with import-path updates. Add one new contract assertion that a producer feature does not need to import `sqlmodel.Session` to use the outbox port.
- **Backwards compatibility**: the CLI move changes the import path used by tooling/scripts. The only in-repo reference is `docs/operations.md:123` (which currently has a typo: `features.auth.management` — corrected to the new path on the way). External scripts or Dockerfiles referencing `src.features.authentication.management:create_super_admin` need a one-line update.

Note: `Makefile:25` references `features.outbox.management retry-failed` — that is a **different** module (the outbox feature owns its own management module). Out of scope for this change.
