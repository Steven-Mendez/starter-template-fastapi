# file-storage Specification

## Purpose
TBD - created by archiving change add-s3-and-resend-adapters. Update Purpose after archive.
## Requirements
### Requirement: FileStoragePort contract

The system SHALL expose a `FileStoragePort` Protocol in `src.features.file_storage.application.ports.file_storage_port` with exactly four methods: `put(key, content, content_type)`, `get(key)`, `delete(key)`, and `signed_url(key, expires_in)`. Every method SHALL return a `Result[T, FileStorageError]`; adapters SHALL NOT raise application-level errors through these methods.

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

### Requirement: S3 adapter is a real boto3 implementation

The system SHALL ship `S3FileStorageAdapter` at `src.features.file_storage.adapters.outbound.s3.adapter` as a real, runnable implementation backed by `boto3`. The adapter SHALL NOT raise `NotImplementedError` from any port method. It SHALL be selectable at composition time by setting `APP_STORAGE_BACKEND=s3` and SHALL pass the same behavioural contract as the local adapter and the in-memory fake.

#### Scenario: S3 adapter passes the FileStoragePort contract suite

- **GIVEN** an `S3FileStorageAdapter` constructed with a `moto`-backed boto3 client
- **WHEN** the `FileStoragePort` contract scenarios are run against it
- **THEN** every scenario passes without an `xfail` or skip marker

#### Scenario: S3 adapter maps NoSuchKey to ObjectNotFoundError

- **GIVEN** an `S3FileStorageAdapter` whose bucket contains no object at key `"missing"`
- **WHEN** `adapter.get("missing")` is called
- **AND** boto3 raises `ClientError` with `Error.Code == "NoSuchKey"`
- **THEN** the adapter returns `Err(ObjectNotFoundError(key="missing"))`

#### Scenario: S3 adapter maps other ClientErrors to StorageBackendError

- **GIVEN** an `S3FileStorageAdapter`
- **WHEN** a port method invocation triggers `botocore.exceptions.ClientError` with a code other than `NoSuchKey`/`404`
- **THEN** the adapter returns `Err(StorageBackendError(reason=...))` carrying a description of the failure

#### Scenario: signed_url validates the object exists

- **GIVEN** an `S3FileStorageAdapter` whose bucket contains no object at key `"missing"`
- **WHEN** `adapter.signed_url("missing", expires_in=60)` is called
- **THEN** the adapter returns `Err(ObjectNotFoundError(key="missing"))`
- **AND** the adapter SHALL NOT return a presigned URL pointing at a non-existent object

#### Scenario: signed_url rejects expires_in above the S3 maximum

- **GIVEN** an `S3FileStorageAdapter`
- **WHEN** `adapter.signed_url("k1", expires_in=604801)` is called
- **THEN** the adapter returns `Err(StorageBackendError(reason=...))` whose reason mentions the 604800-second maximum
- **AND** the adapter SHALL NOT issue a `generate_presigned_url` call to boto3

### Requirement: Local adapter remains the development default

The `LocalFileStorageAdapter` SHALL remain the default when `APP_STORAGE_BACKEND=local` and SHALL continue to write blobs under `APP_STORAGE_LOCAL_PATH` with sha256-prefix sharding. The production settings validator SHALL refuse `APP_STORAGE_BACKEND=local` only when `APP_STORAGE_ENABLED=true`.

#### Scenario: Local backend is accepted in non-production environments

- **GIVEN** `APP_ENVIRONMENT=development`, `APP_STORAGE_ENABLED=true`, `APP_STORAGE_BACKEND=local`, and `APP_STORAGE_LOCAL_PATH=/tmp/storage`
- **WHEN** `AppSettings` is constructed
- **THEN** validation passes

#### Scenario: Local backend is refused in production when enabled

- **GIVEN** `APP_ENVIRONMENT=production`, `APP_STORAGE_ENABLED=true`, and `APP_STORAGE_BACKEND=local`
- **WHEN** `AppSettings` is constructed
- **THEN** validation raises `ValueError` whose message lists the storage-backend mismatch

#### Scenario: Local backend is tolerated when storage is disabled

- **GIVEN** `APP_ENVIRONMENT=production`, `APP_STORAGE_ENABLED=false`, and `APP_STORAGE_BACKEND=local`
- **WHEN** `AppSettings` is constructed
- **THEN** validation passes

### Requirement: Settings select the active adapter

`build_file_storage_container` SHALL instantiate exactly one adapter based on `StorageSettings.backend`, expose it on the returned `FileStorageContainer.port`, and SHALL fail fast with `RuntimeError` if the backend-specific required settings are absent.

#### Scenario: S3 backend without bucket fails fast

- **GIVEN** `StorageSettings(backend="s3", s3_bucket=None, ...)`
- **WHEN** `build_file_storage_container(settings)` is called
- **THEN** the call raises `RuntimeError` whose message names `APP_STORAGE_S3_BUCKET`

#### Scenario: Local backend without path fails fast

- **GIVEN** `StorageSettings(backend="local", local_path=None, ...)`
- **WHEN** `build_file_storage_container(settings)` is called
- **THEN** the call raises `RuntimeError` whose message names `APP_STORAGE_LOCAL_PATH`

### Requirement: Adapters are isolated from inbound layers

No module under `src.features.file_storage.adapters.outbound` SHALL import from `src.features.file_storage.adapters.inbound`, and no feature outside `file_storage` SHALL import an adapter module directly. Consumers SHALL depend on `FileStoragePort` via composition.

#### Scenario: Import-linter contract passes

- **WHEN** `make lint-arch` is run
- **THEN** no contract violation involving `src.features.file_storage` is reported
