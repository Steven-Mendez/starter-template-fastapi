## 1. Move `SEND_EMAIL_JOB` to email.application

- [x] 1.1 Create `src/features/email/application/jobs.py` exporting `SEND_EMAIL_JOB` (the constant currently at `features/email/composition/jobs.py`).
- [x] 1.2 Have `features/email/composition/jobs.py` re-export from the new module for any in-repo callers that still depend on the old path (transient — remove after step 1.4).
- [x] 1.3 Update the two callers (`request_password_reset.py`, `request_email_verification.py`) to import from `features.email.application.jobs`.
- [x] 1.4 Remove the re-export from `composition/jobs.py` once no caller depends on it; keep only the handler factory there.
- [x] 1.5 Add a broad Import Linter contract `Application ↛ Composition (any feature)`: `source_modules = ["features.authentication.application", "features.authorization.application", "features.email.application", "features.background_jobs.application", "features.file_storage.application", "features.outbox.application", "features.users.application"]` with `forbidden_modules = ["features.authentication.composition", "features.authorization.composition", "features.email.composition", "features.background_jobs.composition", "features.file_storage.composition", "features.outbox.composition", "features.users.composition"]`. Single contract covers every present and future application→composition import.
- [x] 1.6 `make lint-arch` passes.

## 2. Abstract the outbox session seam

- [x] 2.1 Declare `OutboxUnitOfWorkPort` in `features/outbox/application/ports/outbox_uow_port.py`:
  ```python
  class OutboxUnitOfWorkPort(Protocol):
      @contextmanager
      def transaction(self) -> Iterator[OutboxWriter]: ...
  ```
  where `OutboxWriter` exposes `enqueue(name, payload)` and `enqueue_at(name, payload, run_at)` against the active transaction.
- [x] 2.2 Implement on the SQLModel adapter: `SQLModelOutboxUnitOfWork` wraps a `sessionmaker` and yields a writer bound to the active session.
- [x] 2.3 Update the producer wiring signature: `build_auth_container(...)` in `src/features/authentication/composition/container.py:111` now takes an `OutboxUnitOfWorkPort` parameter (drop the `outbox_session_factory: SessionScopedOutboxFactory` parameter and the corresponding import at line 70).
- [x] 2.3a Update the call site in `src/main.py:173-176` to pass `outbox.unit_of_work` (or the equivalent attribute on the outbox container) instead of `outbox.session_scoped_factory`.
- [x] 2.3b Adjust the auth repository constructor in `src/features/authentication/adapters/outbound/persistence/sqlmodel/repository.py` to take the `OutboxUnitOfWorkPort` directly; delete the `_outbox_session_factory` field (currently at line 343 and reset at line 354).
- [x] 2.3c Delete the `set_outbox_session_factory(...)` method (`repository.py:359-370`) and the corresponding call in `auth/composition/container.py:131`.
- [x] 2.3d Replace the `if self._outbox_session_factory is None` guard at `repository.py:450` and the `factory(session)` call at line 457 with a `self._outbox_uow.transaction()` block; remove the now-dead `OutboxSessionFactory` alias import.
- [x] 2.4 Delete `SessionScopedOutboxFactory` from `outbox/composition/container.py:38`.
- [x] 2.5 Update `docs/outbox.md` with the new port shape and a worked example.
- [x] 2.6 Add an Import Linter contract `Outbox port consumers do not import sqlmodel`: `source_modules = ["features.authentication.composition", "features.authentication.application"]` (extend with future producers) and `forbidden_modules = ["sqlmodel"]`. Pair with a runtime test that constructs `build_auth_container(...)` with a fake `OutboxUnitOfWorkPort` and never touches a real `Session`.

## 3. Relocate `management.py`

- [x] 3.1 Create `src/cli/__init__.py` and `src/cli/create_super_admin.py`. Move the contents of `src/features/authentication/management.py` into the new file.
- [x] 3.2 Update the wiring inside `create_super_admin.py` to construct containers via each feature's public `composition/container.py` API (the way `main.py` does). Resist re-implementing wiring inline.
- [x] 3.3 Seal the `AuthorizationRegistry` before invoking `BootstrapSystemAdmin` (the current `management.py` does NOT seal — fix this on the way).
- [x] 3.4 `pyproject.toml` declares no script entry point for the CLI today; if added in this PR, point it at `src.cli.create_super_admin:main`.
- [x] 3.5 Update `docs/operations.md:123` "Bootstrapping the first admin" — replace the existing typo'd `uv run python -m features.auth.management create-super-admin ...` with `uv run python -m cli.create_super_admin create-super-admin ...` (or whatever module path matches the final layout under `PYTHONPATH=src`).
- [x] 3.6 Delete `src/features/authentication/management.py`.
- [x] 3.7 Tighten Import Linter: `features.* ↛ src.cli` (CLI is a composition root and may import features, but features must not import CLI).

## 4. Wrap-up

- [x] 4.1 `make ci` green (lint, arch lint, typecheck, tests).
- [x] 4.2 Manual: run the new CLI (`uv run python -m cli.create_super_admin create-super-admin --email ... --password-env ...`) against a clean DB and confirm a super-admin is created. (If `fix-bootstrap-admin-escalation` has not yet landed, the current behavior — promote-on-existing — is unchanged; that change tightens the refusal afterward.)
