# S3 file-storage adapter — operator notes

`S3FileStorageAdapter` is implemented and wired by `build_file_storage_container`
when `APP_STORAGE_BACKEND=s3`. It uses `boto3`'s standard credential
chain (environment variables, shared config, instance profile, …) and
does not introduce any template-specific knob for endpoints — operators
pointing at R2 / MinIO / other S3-compatible services set
`AWS_ENDPOINT_URL_S3` at the SDK level instead.

This page captures the AWS-side configuration the runtime expects.

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
      "Sid": "FileStorageBucketHead",
      "Effect": "Allow",
      "Action": ["s3:ListBucket"],
      "Resource": "arn:aws:s3:::<bucket-name>"
    }
  ]
}
```

`s3:ListBucket` is what S3 evaluates for `head_object` on a missing key —
without it the adapter cannot distinguish "missing object" from
"forbidden", and `signed_url` for an absent key would return a generic
`StorageBackendError` instead of `ObjectNotFoundError`.

`generate_presigned_url` does not need an extra permission — signing
is a local operation against the SDK's credentials.

## Bucket configuration checklist

- **Block public access**: enable all four BPA toggles. Presigned URLs
  still work with BPA on; they sign requests, not policy.
- **Versioning**: optional, but useful for accidental-delete recovery.
- **Lifecycle**: most consumers want a multipart-upload abort rule
  (`AbortIncompleteMultipartUpload` after 7 days) to avoid orphaned
  upload parts incurring storage cost.
- **Encryption**: SSE-S3 is the cheapest correct default. Switch to
  SSE-KMS if compliance requires customer-managed keys (and add
  `kms:GenerateDataKey` to the IAM policy when you do).

## Tests

The adapter is exercised by the shared `FileStoragePort` contract
test (`src/features/file_storage/tests/contracts/`) against an
in-process `moto` mock, plus targeted unit tests for the error-mapping
edges. No real AWS account is touched in CI.
