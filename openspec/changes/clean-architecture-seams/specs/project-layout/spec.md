## MODIFIED Requirements

### Requirement: Application layer does not import composition layers

`features/*/application/` modules SHALL NOT import from any `features/*/composition/` module — neither their own feature's composition nor another feature's. Cross-feature constants needed by application code (job names, template names, registry keys) MUST live in the producing feature's `application/` layer.

The Import Linter configuration SHALL include a contract that fails CI when this rule is violated.

#### Scenario: `application` import of `composition` fails the arch lint

- **GIVEN** a hypothetical commit that imports `features.email.composition.jobs.SEND_EMAIL_JOB` from a use case in `features.authentication.application`
- **WHEN** `make lint-arch` runs
- **THEN** the run fails with a contract violation naming the import

#### Scenario: Own-feature application-to-composition import also fails

- **GIVEN** a hypothetical commit that adds `from features.authentication.composition.container import build_auth_container` to a module under `features/authentication/application/`
- **WHEN** `make lint-arch` runs
- **THEN** the contract names the violating import (the rule applies to a feature's own composition too, not just cross-feature)

### Requirement: Bootstrap CLI lives outside features

The super-admin bootstrap CLI SHALL live at `src/cli/create_super_admin.py`. It MUST construct feature containers via each feature's published `composition/container.py` API; it MUST NOT duplicate wiring inline. It MUST seal the `AuthorizationRegistry` before invoking `BootstrapSystemAdmin`.

`features/*/` directories MUST NOT contain modules whose responsibility is to wire other features (i.e. no second composition root inside a feature).

#### Scenario: `features/*/` does not contain a cross-feature wiring module

- **GIVEN** the repository
- **WHEN** the test scans `src/features/*/` for modules that import more than one other feature's `composition/container.py`
- **THEN** no such module is found

#### Scenario: CLI invocation succeeds against a clean database

- **GIVEN** a clean Postgres database and a valid `.env`
- **WHEN** `uv run python -m src.cli.create_super_admin` is invoked with the bootstrap env vars set
- **THEN** the process exits with status 0 and creates the configured super-admin (subject to the refusal rules introduced by the `fix-bootstrap-admin-escalation` proposal)

#### Scenario: CLI seals the authorization registry before bootstrap

- **GIVEN** a test instantiates the CLI entry point with a fresh `AuthorizationRegistry`
- **WHEN** the CLI invokes `BootstrapSystemAdmin`
- **THEN** the registry's `sealed` flag is `True` at the moment of invocation
- **AND** a unit test that calls the CLI's wiring helper on an already-sealed registry does not raise (sealing is idempotent or the helper checks first)

## ADDED Requirements

### Requirement: OutboxPort exposes a transport-agnostic UnitOfWork seam

The `outbox` capability SHALL declare an `OutboxUnitOfWorkPort` Protocol with a `transaction()` context manager that yields an `OutboxWriter`. The writer SHALL expose `enqueue(name, payload)` and `enqueue_at(name, payload, run_at)` methods. Producer composition modules MUST consume the UnitOfWork port; they MUST NOT depend on a `Callable[[Session], OutboxPort]`-shaped factory or any other type alias whose signature mentions `sqlmodel.Session`.

The auth repository SHALL accept the `OutboxUnitOfWorkPort` directly via its constructor (or `build_auth_container(...)`); the post-hoc `set_outbox_session_factory(...)` registration on the engine-owning repository SHALL NOT exist.

#### Scenario: Producer composition does not depend on a Session-typed alias

- **GIVEN** the import-linter contract `Outbox port consumers do not import sqlmodel`
- **WHEN** `make lint-arch` runs against a tree where `features.authentication.composition.container` imports any name from `sqlmodel`
- **THEN** the run fails with a contract violation naming the import

#### Scenario: Auth repository takes the UoW port at construction

- **GIVEN** the post-rename auth repository
- **WHEN** a test instantiates it with a fake `OutboxUnitOfWorkPort` and immediately calls `issue_internal_token_transaction()`
- **THEN** the call succeeds without an intermediate `set_outbox_session_factory(...)` step
- **AND** `set_outbox_session_factory` is no longer defined on the repository class

#### Scenario: SQLModel adapter implements the new port

- **GIVEN** the outbox SQLModel adapter
- **WHEN** a test instantiates `SQLModelOutboxUnitOfWork(sessionmaker)` and calls `.transaction()`
- **THEN** the yielded writer's `enqueue(...)` call results in a row inserted in the same transaction as any other writes made through the underlying session

#### Scenario: Transaction rolls back the enqueue on error

- **GIVEN** the SQLModel `OutboxUnitOfWorkPort` implementation
- **WHEN** a test enters `transaction()`, calls `writer.enqueue(...)`, and raises before the context exits
- **THEN** no outbox row is persisted (the row is part of the surrounding transaction, which rolls back)
- **AND** a subsequent successful `transaction()` on the same UoW is unaffected by the prior rollback
