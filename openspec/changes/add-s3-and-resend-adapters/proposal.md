## Why

The starter ships `file_storage` and `email` with one real adapter each (`local`, `console`) plus a production-shaped counterpart that's either a stub (`s3` raises `NotImplementedError`) or a self-hosted generic (`smtp`). Operators picking this template for a real deployment hit a wall on day one: they have to implement S3 themselves before any feature can store blobs in production, and `smtp` works but ties them to running their own deliverability stack instead of a modern managed provider. Filling in the S3 stub with `boto3` and adding a `Resend` HTTP adapter gives the template two real "this is what production looks like" options that take zero implementation work to adopt.

## What Changes

- Replace the `S3FileStorageAdapter` stub with a real implementation backed by `boto3`. Bucket and region come from `APP_STORAGE_S3_BUCKET` / `APP_STORAGE_S3_REGION` (already declared). Map `botocore.exceptions.ClientError` codes to `ObjectNotFoundError` / `StorageBackendError`. `signed_url` returns an S3 presigned GET URL bounded by S3's seven-day max.
- Flip the S3 row in `test_file_storage_port_contract.py` from `xfail(strict=True)` to a real test path. The contract suite runs against `moto`'s in-memory S3 (already an ecosystem standard, ~0 setup, doesn't need Docker), so the existing unit-tier marker stays — no new integration tier required for this adapter.
- Add a `ResendEmailAdapter` under `src/features/email/adapters/outbound/resend/` that POSTs the rendered message to `https://api.resend.com/emails` over `httpx`. New backend literal `"resend"`. New env vars `APP_EMAIL_RESEND_API_KEY`, optional `APP_EMAIL_RESEND_BASE_URL` (so tests and self-hosted Resend-compatible APIs can override). Map HTTP 4xx → `DeliveryError(reason=…)`, transport errors → `DeliveryError`, 2xx → `Ok`.
- Extend `EmailSettings`: backend literal becomes `"console" | "smtp" | "resend"`, two new optional fields, `validate()` requires `RESEND_API_KEY` + `EMAIL_FROM` when backend is `resend`, `validate_production()` continues to refuse `console` (resend is allowed).
- Wire the new adapter into `build_email_container`; keep `console` and `smtp` exactly as they are. The Resend adapter participates in the existing email contract test parametrisation via a `respx`-mocked HTTP client (already supported by `httpx`).
- Add `boto3` and `moto` (test dep) to `pyproject.toml`. Promote `httpx` from dev dep to runtime dep (the Resend adapter needs it at request time). Add `respx` as a dev dep for mocking the Resend HTTP calls.
- Update `docs/file-storage.md` and `docs/email.md`: remove the "stub" language for S3, add a Resend section with API key acquisition + base URL override, update the env-var tables in both docs and `docs/operations.md` + `CLAUDE.md`.

This change does **not** touch `background_jobs`: in-process + arq cover dev and production already. No new feature consumer wires `FileStoragePort` in this change either — the adapter ships ready, but `APP_STORAGE_ENABLED` stays `false` by default and the production validator only refuses `local` when a consumer flips it on.

## Capabilities

### New Capabilities
- `file-storage`: codifies the `FileStoragePort` contract (put/get/delete/signed_url semantics), the backend-selection rules, and the adapter expectations for `local`, `s3`, and the in-memory fake. The capability does not yet exist as a spec; this change introduces it because the S3 adapter is now a real implementation worth pinning down.
- `email`: codifies the `EmailPort` contract, the template-registry seal lifecycle, and the per-backend rules for `console`, `smtp`, and `resend`. Same rationale — adding Resend is the first time `email` has more than one production-shaped path, so the requirements are worth nailing down.

### Modified Capabilities
<!-- None: file-storage and email do not have prior specs under openspec/specs/. The two capabilities are introduced as new in this change. -->

## Impact

- **Code**:
  - `src/features/file_storage/adapters/outbound/s3/adapter.py` (rewrite from stub to real)
  - `src/features/file_storage/adapters/outbound/s3/__init__.py` (no change expected)
  - `src/features/file_storage/adapters/outbound/s3/README.md` (delete or repurpose as "operator notes")
  - `src/features/file_storage/tests/contracts/test_file_storage_port_contract.py` (S3 path becomes real, backed by `moto`)
  - `src/features/email/adapters/outbound/resend/{__init__.py,adapter.py}` (new)
  - `src/features/email/composition/{settings.py,container.py}` (new backend + wiring)
  - `src/features/email/tests/contracts/test_email_port_contract.py` (parametrise the Resend adapter with `respx`)
  - `src/platform/config/settings.py` (new env vars, updated `Literal` on `email_backend`)
- **Dependencies**: `boto3~=1.34` and `httpx~=0.28` move into runtime deps; `moto~=5.0` and `respx~=0.21` join dev deps. `boto3` adds ~25 MB to the install footprint, accepted because S3 is now a real ship-able backend.
- **Configuration**: new env vars `APP_EMAIL_RESEND_API_KEY`, `APP_EMAIL_RESEND_BASE_URL` (optional, default `https://api.resend.com`). `APP_EMAIL_BACKEND` accepts a third value `resend`. `APP_STORAGE_BACKEND=s3` now actually works at runtime.
- **Docs**: `docs/file-storage.md`, `docs/email.md`, `docs/operations.md`, `CLAUDE.md` env-var tables, the `s3/README.md` operator-policy notes (kept for IAM/bucket policy reference) all get updated.
- **Out of scope**: SES, GCS, Azure Blob, SQS adapters; wiring `FileStoragePort` into a real consumer feature; multipart-upload support; attachment support in `EmailPort`.
