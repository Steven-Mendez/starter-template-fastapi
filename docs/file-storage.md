# File Storage

The `file_storage` feature owns persistent-blob access. It ships with a port,
a local-filesystem adapter, and a real `boto3`-backed S3 adapter. No consumer
feature wires it in the current source tree; it ships as scaffolding ready
to plug into your own feature.

## At A Glance

| Piece | Where |
| --- | --- |
| Port | `src/features/file_storage/application/ports/file_storage_port.py` — `FileStoragePort.put`, `.get`, `.delete`, `.list`, `.signed_url` |
| Local adapter | `src/features/file_storage/adapters/outbound/local/` |
| S3 adapter | `src/features/file_storage/adapters/outbound/s3/` (`boto3`-backed) |
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

### S3 (`S3FileStorageAdapter`)

Backed by `boto3`. Credentials come from the standard AWS chain
(environment variables, shared config, EC2 / ECS / EKS instance profile,
SSO, etc.) — no template-specific knob.

- `put` → `s3_client.put_object`
- `get` → `s3_client.get_object`; `NoSuchKey` / 404 is mapped to `ObjectNotFoundError`
- `delete` → `s3_client.delete_object` (already idempotent on S3)
- `signed_url` calls `head_object` first (so a missing key returns
  `ObjectNotFoundError` instead of a URL that 404s), then
  `generate_presigned_url`. `expires_in > 604800` (S3's 7-day SigV4
  maximum) is rejected as `StorageBackendError`.

Every other `botocore.exceptions.ClientError` (and `BotoCoreError` /
`EndpointConnectionError`) is wrapped as `StorageBackendError(reason=...)`.

#### Pointing at R2 / MinIO / other S3-compatible services

The adapter does not expose an `endpoint_url` setting. Set
`AWS_ENDPOINT_URL_S3` (or `AWS_ENDPOINT_URL`) at the process level and
`boto3` picks it up natively — no code changes required.

#### AWS setup

The IAM policy and bucket-configuration checklist live in
`src/features/file_storage/adapters/outbound/s3/README.md`.

### Fake (`FakeFileStorage`)

In-memory implementation used by unit tests. Mirrors the contract test
suite so the fake and the local adapter exercise the same behavior.

## Contract Tests

`src/features/file_storage/tests/contracts/` runs the same assertions
against all three adapters:

- the fake (always),
- the local adapter (always),
- the S3 adapter, exercised in-process against `moto`'s AWS mock —
  no Docker required.

## Per-User Prefix And Account Lifecycle

Blobs that belong to a specific user MUST be written under the per-user
prefix `users/{user_id}/`. The users feature ships a default
`UserAssetsCleanupPort` implementation
(`FileStorageUserAssetsAdapter`) that walks this prefix on
`FileStoragePort` and deletes every blob it finds.

Cleanup is **always asynchronous** — `DeactivateUser` (and, when it
lands, `EraseUser`) enqueue a `delete_user_assets` job through the
outbox in the same transaction that mutates the user. The worker
resolves `UserAssetsCleanupPort` from the users container and invokes
`delete_user_assets(user_id)` out of band.

Two rules follow from this:

- **Never call `UserAssetsCleanupPort.delete_user_assets` inline from a
  use case.** Direct invocation couples the HTTP path to backend
  latency and loses the worker's exponential-backoff retry on
  transient failures. The composition root only wires the port into
  the `delete_user_assets` job handler — there is no use-case-level
  injection.
- **Adopt the prefix in your uploaders.** A feature that stores
  user-owned blobs at `attachments/{ulid}` rather than under
  `users/{user_id}/...` will leak orphans on deactivation. If your
  feature must use a different layout, ship its own
  `UserAssetsCleanupPort` adapter and register it instead.

The handler is idempotent: when the prefix is empty (already cleaned
or never used), the call returns `Ok(None)` and the outbox row reaches
`delivered` on the first relay tick.

## Extending The Feature

- **Add a different cloud** (Azure Blob, GCS): implement `FileStoragePort`
  and wire it in `build_file_storage_container`. Contract tests should pass
  without modification.
- **Server-side encryption** / SSE-KMS: pass adapter-specific options into
  the adapter's constructor; keep the port signature stable.
- **Range reads, multi-part uploads**: extend the port carefully —
  contract tests must continue to assert the basic round-trip behavior of
  every adapter, including the fake.
