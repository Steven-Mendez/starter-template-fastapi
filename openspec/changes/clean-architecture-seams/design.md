## Depends on

(none) — this change lands first in the architecture/lifecycle cluster.

## Conflicts with

- `fix-bootstrap-admin-escalation` — both touch `BootstrapSystemAdmin`. After this change relocates `src/features/authentication/management.py` to `src/cli/create_super_admin.py`, the downstream change must rebase its file paths.
- `make-auth-flows-transactional` — both touch `src/features/authentication/composition/container.py`. This change lands first; the auth-transactional change rebases.
- `add-error-reporting-seam` — both touch `create_app()` wiring in `src/app_platform/api/app_factory.py`. No hard ordering required; flag merge friction.
- `harden-auth-defense-in-depth`, `invalidate-previous-issuance-tokens` — both edit `request_password_reset.py` and `request_email_verification.py`. Land this change (port relocation) first; downstream changes rebase against the new import paths.

## Context

The architecture audit (see synthesis report) flagged three places where the layering rules are honored to the letter and violated in spirit. These aren't bugs that produce wrong answers; they're patterns that, once copied, slowly erode the boundary. Fixing them now (before more features are added) keeps the template's main selling point — clean hex with explicit cross-feature seams — intact.

The three issues are independent in code but share a root cause: each one is a place where the easy path was chosen over the layered path. Each fix is small and reviewable in isolation; we bundle them because they share lint-contract changes and because reviewing them together makes the seam story coherent.

## Goals / Non-Goals

**Goals**
- `application` never imports `composition` (own feature or otherwise). Constants and shared facts live in `application` or `domain`.
- `OutboxPort` consumers do not need to know about SQLModel.
- The bootstrap CLI lives in a project-level composition root, not inside a feature.

**Non-Goals**
- Generalizing the outbox port to support non-DB transports. The port shape changes; the implementation stays SQLModel-only.
- Refactoring the inbound-HTTP layer or the FastAPI app factory. Out of scope.
- Wholesale move of all per-feature scripts to `src/cli/`. Only `management.py` (which is the second composition root) moves; per-feature CLI helpers that genuinely belong to one feature stay.

## Decisions

### Decision 1: `SEND_EMAIL_JOB` lives in `email.application.jobs`

- **Chosen**: pure-data constants describing the email-feature contract belong to its application layer. Composition layers should only ship *factories* and *registry hooks*, not the names of things that other features need.
- **Rejected**: leave the constant in `composition` and add a per-import-line `# noqa` in lint. Maintenance nightmare; signals the wrong message to contributors.

### Decision 2: New `OutboxUnitOfWorkPort` over patching the existing factory

- **Chosen**: a dedicated port that exposes `transaction()` returning an `OutboxWriter`. Producers' composition depends on the port; the SQLModel adapter is one implementation, owning a `sessionmaker` internally. Future Mongo-backed implementations can satisfy the port too (yields a `MotorWriter` or similar).
- **Rejected**: keep the `Callable[[Session], OutboxPort]` shape and add a `# noqa` or move the `Session` type alias to an outbox-owned re-export. Doesn't actually abstract; just makes the leak less obvious.
- **Rejected**: have producers' composition depend on `sqlmodel.Session` directly. Already what we have; this proposal exists to fix exactly that.

The change also removes the post-hoc `SQLModelAuthRepository.set_outbox_session_factory(...)` registration (`adapters/outbound/persistence/sqlmodel/repository.py:359-370`) — the docstring explicitly flags it as a workaround. After this change, the auth repository constructor takes the `OutboxUnitOfWorkPort` directly via `build_auth_container(...)`, eliminating the two-step "construct then register" dance and the `_outbox_session_factory: OutboxSessionFactory | None = None` nullable field that the rest of the repository must guard.

### Decision 3: CLI lives at `src/cli/`, not `src/management/` or `tools/`

- **Chosen**: `src/cli/create_super_admin.py`. Matches the "src layout" convention; flat enough to discover; clear contract that anything in `src/cli/` is allowed to import composition roots of any feature.
- **Rejected**: `tools/` at the repo root. Splits the project across two roots; `src.cli.*` is more uniform.
- **Rejected**: `src/management/`. Pre-existing baggage from Django world; the directory name "management" already misled us once.

## Risks / Trade-offs

- **Risk**: external scripts or Dockerfiles reference `src.features.authentication.management:create_super_admin`. Mitigation: in-repo, the only reference is `docs/operations.md:123` (which currently has a typo: `features.auth.management`). `pyproject.toml` declares no script entry point for the CLI today. Update the doc and the `python -m` invocation in one step.
- **Risk**: the new `OutboxUnitOfWorkPort` adds API surface. Mitigation: it has exactly one method, returning a tiny writer object with exactly two methods. The total exposed surface is smaller than the previous `SessionScopedOutboxFactory` once you account for `sqlmodel.Session`'s API.
- **Trade-off**: lint-contract churn (one new ignore-list removal, one new rule). Acceptable cost for the spec tightening.

## Migration Plan

Single PR. Order:

1. Move `SEND_EMAIL_JOB` and update lint contract.
2. Define `OutboxUnitOfWorkPort`; implement on SQLModel adapter; update producer wiring; delete the old factory.
3. Relocate `management.py` → `src/cli/create_super_admin.py`; seal the authz registry on the way; update lint contract.
4. `make ci`.

Rollback: revert. No persistence side effects; no public API changes (the CLI is invoked by humans, not other code).
