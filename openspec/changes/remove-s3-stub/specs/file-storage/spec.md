## REMOVED Requirements

### Requirement: S3 adapter is a real boto3 implementation

**Reason**: ROADMAP ETAPA I step 7 removes the non-`local` (non-AWS-shaped) production file-storage backend. Despite the ROADMAP/brief wording ("stub raising `NotImplementedError`"), the adapter was a fully implemented, contract-tested `boto3` implementation; it is deleted in full along with the `APP_STORAGE_BACKEND=s3` selector, the `APP_STORAGE_S3_*` settings, the `s3` dependency extra, and the `moto`-backed contract arm. `FileStoragePort`, the `local` adapter, and the in-memory fake remain. A real, explicitly AWS-shaped `aws_s3` adapter is added at a later roadmap step; this requirement is re-introduced (in AWS-adapter terms) by that change.

**Migration**: Deployments must not set `APP_STORAGE_BACKEND=s3` — the only accepted value is `local` (dev/test), and production refuses `local` when `APP_STORAGE_ENABLED=true`. Production file storage is unavailable until the real AWS S3 adapter is added at a later roadmap step. Projects that do not wire `FileStoragePort` leave `APP_STORAGE_ENABLED=false` and are unaffected. Stale `APP_STORAGE_S3_*` env vars are silently ignored (`AppSettings.model_config` uses `extra="ignore"`).

## MODIFIED Requirements

### Requirement: FileStoragePort contract

The system SHALL expose a `FileStoragePort` Protocol in `src.features.file_storage.application.ports.file_storage_port` with exactly four methods: `put(key, content, content_type)`, `get(key)`, `delete(key)`, and `signed_url(key, expires_in)`. Every method SHALL return a `Result[T, FileStorageError]`; adapters SHALL NOT raise application-level errors through these methods. The port contract is backend-neutral and SHALL NOT name a specific cloud provider in its docstrings as a shipped adapter.

#### Scenario: Put then get returns the same bytes

- **GIVEN** any wired `FileStoragePort` implementation
- **WHEN** `port.put("k1", b"hello", "text/plain")` returns `Ok(None)`
- **AND** `port.get("k1")` is called
- **THEN** the call returns `Ok(b"hello")`

#### Scenario: Get of a missing key returns ObjectNotFoundError

- **GIVEN** any wired `FileStoragePort` implementation with no object at key `"missing"`
- **WHEN** `port.get("missing")` is called
- **THEN** the call returns `Err(ObjectNotFoundError(key="missing"))`

#### Scenario: Delete of a missing key is a no-op

- **GIVEN** any wired `FileStoragePort` implementation with no object at key `"never-existed"`
- **WHEN** `port.delete("never-existed")` is called
- **THEN** the call returns `Ok(None)`

#### Scenario: Put overwrites an existing object

- **GIVEN** any wired `FileStoragePort` implementation
- **WHEN** `port.put("k1", b"first", "text/plain")` is called
- **AND** `port.put("k1", b"second", "text/plain")` is called
- **AND** `port.get("k1")` is called
- **THEN** the final call returns `Ok(b"second")`

#### Scenario: Contract suite exercises only the fake and local adapters

- **GIVEN** `src/features/file_storage/tests/contracts/test_file_storage_port_contract.py`
- **WHEN** its parametrisation is inspected
- **THEN** the only adapter factories are the in-memory fake and the local on-disk adapter
- **AND** no parametrisation id, factory, fixture, or import references an S3/`boto3`/`moto` adapter

### Requirement: Local adapter remains the development default

The `LocalFileStorageAdapter` SHALL be the only file-storage adapter and SHALL be the value when `APP_STORAGE_BACKEND=local` and SHALL continue to write blobs under `APP_STORAGE_LOCAL_PATH` with sha256-prefix sharding. The production settings validator SHALL refuse `APP_STORAGE_BACKEND=local` only when `APP_STORAGE_ENABLED=true`, and SHALL NOT accept any file-storage backend in production (there is no production file-storage transport until the real AWS S3 adapter is added at a later roadmap step). The validator's refusal message SHALL NOT instruct the operator to configure `s3` or set `APP_STORAGE_S3_BUCKET`, and SHALL retain the literal substring `APP_STORAGE_BACKEND`.

#### Scenario: Local backend is accepted in non-production environments

- **GIVEN** `APP_ENVIRONMENT=development`, `APP_STORAGE_ENABLED=true`, `APP_STORAGE_BACKEND=local`, and `APP_STORAGE_LOCAL_PATH=/tmp/storage`
- **WHEN** `AppSettings` is constructed
- **THEN** validation passes

#### Scenario: Local backend is refused in production when enabled

- **GIVEN** `APP_ENVIRONMENT=production`, `APP_STORAGE_ENABLED=true`, and `APP_STORAGE_BACKEND=local`
- **WHEN** `AppSettings` is constructed
- **THEN** validation raises `ValidationError`
- **AND** the message contains the substring `APP_STORAGE_BACKEND`
- **AND** the message names no removed backend (it does not instruct configuring `s3` or setting `APP_STORAGE_S3_BUCKET`)

#### Scenario: Local backend is tolerated when storage is disabled

- **GIVEN** `APP_ENVIRONMENT=production`, `APP_STORAGE_ENABLED=false`, and `APP_STORAGE_BACKEND=local`
- **WHEN** `AppSettings` is constructed
- **THEN** validation passes for the storage axis

#### Scenario: No S3 backend value is accepted

- **GIVEN** `StorageSettings.from_app_settings(backend="s3", ...)`
- **WHEN** the projection is constructed
- **THEN** it raises `ValueError` whose message names only `'local'` as the accepted backend

### Requirement: Settings select the active adapter

`build_file_storage_container` SHALL instantiate exactly one adapter based on `StorageSettings.backend`, expose it on the returned `FileStorageContainer.port`, and SHALL fail fast with `RuntimeError` if the backend-specific required settings are absent. `StorageBackend` SHALL be `Literal["local"]`; there SHALL be no `s3` arm, no `boto3` import (deferred or otherwise), and no `s3_bucket`/`s3_region` field on `StorageSettings` or `storage_s3_*` field on `AppSettings`.

#### Scenario: Local backend without path fails fast

- **GIVEN** `StorageSettings(backend="local", local_path=None, ...)`
- **WHEN** `build_file_storage_container(settings)` is called
- **THEN** the call raises `RuntimeError` whose message names `APP_STORAGE_LOCAL_PATH`

#### Scenario: Local is the only constructible backend

- **GIVEN** the `StorageBackend` type alias and `StorageSettings.from_app_settings`
- **WHEN** they are inspected
- **THEN** `StorageBackend` is `Literal["local"]`
- **AND** `from_app_settings` exposes no `s3_bucket`/`s3_region` parameter and reads no `app.storage_s3_*` attribute

### Requirement: Adapters are isolated from inbound layers

No module under `src.features.file_storage.adapters.outbound` SHALL import from `src.features.file_storage.adapters.inbound`, and no feature outside `file_storage` SHALL import an adapter module directly. Consumers SHALL depend on `FileStoragePort` via composition. After the S3 adapter removal the only outbound adapter module is the local on-disk adapter.

#### Scenario: Import-linter contract passes

- **WHEN** `make lint-arch` is run
- **THEN** no contract violation involving `src.features.file_storage` is reported

#### Scenario: No S3 adapter module remains

- **WHEN** the repository tree is inspected
- **THEN** `src/features/file_storage/adapters/outbound/s3/` does not exist
- **AND** the only outbound adapter package under `src/features/file_storage/adapters/outbound/` is `local`
