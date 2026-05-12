# File Storage

The `file_storage` feature owns persistent-blob access. It ships with a port,
a local-filesystem adapter, and an S3 stub. No consumer feature wires it in
the current source tree; it ships as scaffolding ready to plug into your
own feature.

## At A Glance

| Piece | Where |
| --- | --- |
| Port | `src/features/file_storage/application/ports/file_storage_port.py` — `FileStoragePort.put`, `.get`, `.delete`, `.signed_url` |
| Local adapter | `src/features/file_storage/adapters/outbound/local/` |
| S3 stub | `src/features/file_storage/adapters/outbound/s3/` |
| Fake (for tests) | `src/features/file_storage/tests/fakes/` |
| Settings | `src/features/file_storage/composition/settings.py` (`StorageSettings`) |
| Container | `src/features/file_storage/composition/container.py` |

## Configuration

| Variable | Default | Notes |
| --- | --- | --- |
| `APP_STORAGE_ENABLED` | `false` | Set `true` once a consumer feature wires `FileStoragePort`. |
| `APP_STORAGE_BACKEND` | `local` | One of `local`, `s3`. **Production refuses `local` when `APP_STORAGE_ENABLED=true`.** |
| `APP_STORAGE_LOCAL_PATH` | unset | Filesystem root for the local adapter. Required when backend is `local`. |
| `APP_STORAGE_S3_BUCKET` | unset | Required when backend is `s3`. |
| `APP_STORAGE_S3_REGION` | `us-east-1` | AWS region for the bucket. |

`APP_STORAGE_ENABLED` exists so projects that never use file storage are not
forced to set up S3 in production. The production validator only fires when
a consumer feature has actually wired the port.

## How To Use The Port

In your feature's use case:

```python
class UploadAttachment:
    def __init__(self, storage: FileStoragePort) -> None:
        self._storage = storage

    def execute(self, *, key: str, body: bytes, content_type: str) -> Result[str, ...]:
        self._storage.put(key=key, body=body, content_type=content_type)
        return Ok(self._storage.signed_url(key=key, expires_in=3600))
```

Compose the port into your feature container by taking
`file_storage.port` as a constructor argument in `main.py`. No feature is
allowed to import an adapter directly; Import Linter enforces this.

## Adapters

### Local (`LocalFileStorageAdapter`)

Writes blobs under `APP_STORAGE_LOCAL_PATH`. Keys are sharded into sha256
prefix directories so a single directory never grows unbounded. Useful for
local development and integration tests; production refuses to start with
this adapter when `APP_STORAGE_ENABLED=true`.

`signed_url(...)` returns a `file://` URL — useful for tests, useless for
browsers.

### S3 stub (`S3FileStorageAdapter`)

Every method raises `NotImplementedError`. The `README.md` next to the
adapter describes the boto3 mapping and the IAM permissions a real
implementation needs (`s3:PutObject`, `s3:GetObject`, `s3:DeleteObject`,
plus `s3:GetObject` on a different ARN for presigned URLs).

The stub mirrors the SpiceDB authorization stub: the port's shape is fixed
by the codebase, and filling in the adapter is one of the first things a
consumer who needs S3 will do.

### Fake (`FakeFileStorage`)

In-memory implementation used by unit tests. Mirrors the contract test
suite so the fake and the local adapter exercise the same behavior.

## Contract Tests

`src/features/file_storage/tests/contracts/` runs the same assertions
against all three adapters:

- the fake (always),
- the local adapter (always),
- the S3 stub (skipped with `xfail` until the real implementation lands).

When you implement the S3 adapter, flip the contract test from `xfail` to
`xpass` and provide testcontainers (e.g. `minio`) or a moto fixture.

## Extending The Feature

- **Add a different cloud** (Azure Blob, GCS): implement `FileStoragePort`
  and wire it in `build_file_storage_container`. Contract tests should pass
  without modification.
- **Server-side encryption** / SSE-KMS: pass adapter-specific options into
  the adapter's constructor; keep the port signature stable.
- **Range reads, multi-part uploads**: extend the port carefully —
  contract tests must continue to assert the basic round-trip behavior of
  every adapter, including the fake.
