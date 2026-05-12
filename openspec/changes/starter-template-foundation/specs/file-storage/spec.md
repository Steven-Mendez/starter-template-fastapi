## ADDED Requirements

### Requirement: File-storage is a self-contained feature slice

The system SHALL host file-storage concerns in a dedicated feature slice at `src/features/file_storage/`. The slice SHALL contain the `FileStoragePort` inbound port, a `local` adapter that writes to a filesystem path, and an `s3` adapter stub that raises `NotImplementedError`. The slice SHALL NOT import from any other feature.

#### Scenario: File-storage owns its port and adapters

- **WHEN** the codebase is loaded
- **THEN** `src/features/file_storage/application/ports/file_storage_port.py` defines `FileStoragePort` as a Protocol with the methods `put(key, content, content_type)`, `get(key)`, `delete(key)`, and `signed_url(key, expires_in)`
- **AND** `src/features/file_storage/adapters/outbound/local/` and `src/features/file_storage/adapters/outbound/s3/` each contain an adapter that implements `FileStoragePort`

#### Scenario: File-storage does not import from other features

- **WHEN** the codebase is loaded
- **THEN** no module under `src/features/file_storage/` imports from any other `src/features/<name>/` directory

### Requirement: Adapter selection by configuration

The system SHALL select the storage adapter at startup from `APP_STORAGE_BACKEND`, which accepts `local` or `s3`. When `local` is selected, `APP_STORAGE_LOCAL_PATH` SHALL be required and SHALL point to a writable directory. When `s3` is selected, calls to the adapter SHALL raise `NotImplementedError` with a message pointing at the adapter's README.

#### Scenario: Local adapter round-trips bytes

- **GIVEN** `APP_STORAGE_BACKEND=local` and `APP_STORAGE_LOCAL_PATH` set to a writable directory
- **WHEN** `FileStoragePort.put("k1", b"hello", "text/plain")` is called and then `FileStoragePort.get("k1")` is called
- **THEN** the second call returns `b"hello"`
- **AND** the first call wrote a file under `APP_STORAGE_LOCAL_PATH` whose name is derived from `"k1"`

#### Scenario: Local adapter signed_url returns a path or URL the consumer can serve

- **GIVEN** the local adapter is selected
- **WHEN** `FileStoragePort.signed_url("k1", expires_in=60)` is called
- **THEN** the result is a `file://` URL pointing at the on-disk file
- **AND** the result is a string

#### Scenario: S3 stub raises with a helpful message

- **GIVEN** `APP_STORAGE_BACKEND=s3`
- **WHEN** any method on the s3 adapter is called
- **THEN** the call raises `NotImplementedError`
- **AND** the message points to the adapter's README

### Requirement: Port has at least one working adapter under test

Import Linter SHALL enforce that `FileStoragePort` has at least one adapter under test in the repository. The local adapter SHALL be exercised by a contract-test suite that runs against both the in-memory fake and the on-disk adapter, so the contract is not just type-checked but behaviorally verified.

#### Scenario: Local adapter passes the same contract tests as the fake

- **WHEN** the contract-test suite runs
- **THEN** every contract test passes against the in-memory fake
- **AND** every contract test passes against the on-disk local adapter
