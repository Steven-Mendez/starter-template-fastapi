# S3 file-storage adapter (stub)

`S3FileStorageAdapter` is intentionally left unimplemented. It ships
as scaffolding so the `FileStoragePort` has a production-shaped
counterpart to the local adapter, and so consumer projects can fill
it in without rediscovering the port shape.

This page captures the implementation contract: which boto3 calls map
to which port methods, and what IAM permissions the runtime needs.

## Dependency

Add `boto3` to `pyproject.toml`:

```toml
dependencies = [
  # …
  "boto3~=1.34",
]
```

`boto3` is heavy (~25 MB installed) and locks the project to AWS, so
it is not added until a consumer needs it.

## Method ↔ boto3 mapping

| Port method | boto3 call | Notes |
|---|---|---|
| `put(key, content, content_type)` | `s3_client.put_object(Bucket=…, Key=key, Body=content, ContentType=content_type)` | Overwrite-by-default matches the port contract. |
| `get(key)` | `s3_client.get_object(Bucket=…, Key=key)["Body"].read()` | Translate `botocore.exceptions.ClientError` with `Error.Code == "NoSuchKey"` to `ObjectNotFoundError`. |
| `delete(key)` | `s3_client.delete_object(Bucket=…, Key=key)` | S3 deletes are already idempotent — no special handling needed for missing keys. |
| `signed_url(key, expires_in)` | `s3_client.generate_presigned_url("get_object", Params={"Bucket": …, "Key": key}, ExpiresIn=expires_in)` | Validate `expires_in ≤ 604800` (S3's one-week maximum). |

All other `botocore.exceptions.ClientError` instances should be wrapped
in `StorageBackendError(reason=str(exc))` so consumers always see a
`Result[..., FileStorageError]` regardless of the backend.

## IAM policy

The runtime principal (IAM role for ECS/EKS, IAM user for self-hosted)
needs the following actions on the bucket and its objects:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "FileStorageObjectAccess",
      "Effect": "Allow",
      "Action": [
        "s3:GetObject",
        "s3:PutObject",
        "s3:DeleteObject"
      ],
      "Resource": "arn:aws:s3:::<bucket-name>/*"
    },
    {
      "Sid": "FileStorageBucketList",
      "Effect": "Allow",
      "Action": ["s3:ListBucket"],
      "Resource": "arn:aws:s3:::<bucket-name>"
    }
  ]
}
```

`signed_url` does not need an extra permission — `generate_presigned_url`
is a local operation against the SDK's credentials.

## Bucket configuration checklist

- **Block public access**: enable all four BPA toggles. Presigned URLs
  still work with BPA on; they sign requests, not policy.
- **Versioning**: optional, but useful for accidental-delete recovery.
- **Lifecycle**: most consumers want a multipart-upload abort rule
  (`AbortIncompleteMultipartUpload` after 7 days) to avoid orphaned
  upload parts incurring storage cost.
- **Encryption**: SSE-S3 is the cheapest correct default. Switch to
  SSE-KMS if compliance requires customer-managed keys.

## Tests

Once implemented, the contract tests in
`src/features/file_storage/tests/contracts/test_file_storage_port_contract.py`
should run against a real S3 client backed by `moto` (the boto3 test
double). The existing skip marker for the stub can be removed.
