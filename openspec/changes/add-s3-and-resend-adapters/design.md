## Context

`file_storage` and `email` follow the same hexagonal shape as every other feature in the template: a narrow `Port` Protocol in `application/ports/`, a `Container` selected by a `Settings` literal, and one or more `Adapter` classes under `adapters/outbound/`. Both features already have the wiring, contract tests, and production-validation hooks. What's missing is a credible **second** real adapter:

- `file_storage` ships `local` (real, dev) and `s3` (a stub that raises `NotImplementedError` from every method). The stub's `README.md` already documents the intended boto3 mapping and IAM policy.
- `email` ships `console` (real, dev/test) and `smtp` (real, generic). SMTP works but is the old-world option; modern teams pick a managed HTTP API (Resend, Postmark, SES, Mailgun) for better DX and deliverability.

Operators evaluating the template can adopt `local` and `console` for development immediately, but the moment they aim at production they have to either write the S3 adapter themselves or settle for SMTP. This change closes both gaps without touching any other feature.

## Goals / Non-Goals

**Goals:**
- Ship a real `S3FileStorageAdapter` backed by `boto3`, exercised by the same contract tests the fake and local adapters already pass — no special integration tier required.
- Ship a real `ResendEmailAdapter` backed by `httpx` and the Resend HTTP API, exercised by the email contract suite via `respx`-mocked transport.
- Keep the existing public surface stable: no new ports, no breaking changes to the existing `console`/`smtp`/`local` adapters, no changes to feature consumers.
- Keep installation cheap when the operator doesn't need these adapters — `boto3` adds runtime weight but the project already pulls in heavy deps (OpenTelemetry, SQLModel, FastAPI); `httpx` was already a dev dep and only moves tier.

**Non-Goals:**
- AWS SES, GCS, Azure Blob, Postmark, Mailgun adapters. The change is "one popular managed backend per feature," not "every backend."
- SQS or any change to `background_jobs`. The in-process + arq combo covers dev and production already.
- Multipart uploads, range reads, server-side encryption knobs on the S3 adapter beyond what `boto3` does by default. A future change can extend the port.
- Wiring `FileStoragePort` into a real consumer feature. `_template` is the only feature that could plausibly use it, and `remove-template-feature` is removing it. A future feature will pick the port up when it ships.
- Attachment support, HTML bodies, or template-driven subject/body separation on the Resend adapter — match what `smtp` does today and no more.
- Moving the `s3` contract assertions into a separate `integration` marker. `moto` runs in-process and is fast; the existing `unit` marker stays.

## Decisions

### D1. `boto3` over `aioboto3`

The codebase's adapters are sync — `LocalFileStorageAdapter`, `SmtpEmailAdapter`, `SQLModelAuthorizationAdapter`. FastAPI's threadpool runs sync route deps off the event loop, so a sync S3 adapter does not block. Adding `aioboto3` would mean async/sync coexistence inside one feature, and `boto3` has the broader ecosystem (`moto` is sync, signed-URL generation is sync, every example in the AWS docs is sync). Stick with `boto3`.

Alternative considered: `aioboto3` for non-blocking I/O. Rejected — the rest of the codebase's adapters are sync, mixing modes would be the only async oddity in the tree, and the throughput gain doesn't matter at the scale this template targets.

### D2. Client lifecycle: build once, reuse for the process

`boto3.client("s3")` is cheap to construct but does TCP/TLS handshake on first call. The adapter is a `@dataclass(slots=True)` built once in `build_file_storage_container` and held on `app.state.file_storage` for the process lifetime. The `boto3.client` instance is created in `__post_init__` (or via `field(default_factory=...)`) and stored on the adapter. Threadsafety: `botocore` clients are documented as threadsafe for read paths; FastAPI's threadpool will reuse the same client across requests.

Alternative considered: client-per-call. Rejected — extra latency on every operation for no isolation benefit. The adapter has no mutable state worth isolating.

### D3. Error mapping (S3)

`botocore.exceptions.ClientError` is the catch-all. The adapter translates known codes:

| boto3 condition | Port result |
| --- | --- |
| `get_object` → `ClientError` with `Error.Code in {"NoSuchKey", "404"}` | `Err(ObjectNotFoundError(key))` |
| `head_object` 404 inside `signed_url` | `Err(ObjectNotFoundError(key))` (matches local's "must exist" semantics) |
| Any other `ClientError` | `Err(StorageBackendError(reason=…))` |
| `botocore.exceptions.EndpointConnectionError`, `BotoCoreError` | `Err(StorageBackendError(reason=…))` |

`put_object`, `delete_object`, and `generate_presigned_url` do not raise on the "missing object" path. `delete_object` is already idempotent on S3 (it returns 204 even when the key is absent), matching the port contract (`delete` of a missing key is `Ok`).

Alternative considered: a single catch-all `StorageBackendError` for every failure. Rejected — the port's contract gives consumers `ObjectNotFoundError` as a first-class case so they can return 404 from HTTP routes without inspecting strings; the S3 adapter must preserve that.

### D4. `signed_url` validates existence

The local adapter's `signed_url` errors on a missing key. S3's `generate_presigned_url` is a local operation that signs blindly — it returns a string even for a key that doesn't exist, and the URL will 403 when used. To keep contract parity, the S3 adapter does a `head_object` first and returns `ObjectNotFoundError` when the key is absent. This adds one extra S3 API call per signing, accepted because signed URLs are not on a hot path and the parity is worth more than the millisecond.

`expires_in` is clamped to S3's hard maximum (604800 seconds / 7 days) — values above that are rejected as `StorageBackendError(reason="expires_in exceeds S3 maximum of 604800 seconds")` rather than silently truncated, so callers see a real error instead of a URL that fails later.

Alternative considered: skip the `head_object` and accept that S3 signed URLs are "signing-only". Rejected — divergent contracts across adapters violate the "fakes and reals pass the same contract" principle the codebase is built on.

### D5. Resend transport: `httpx` over `requests`

Project ergonomic alignment: `httpx` is already used in the test suite (FastAPI's `TestClient` is built on it), and it supports both sync and async clients with the same API. The Resend adapter is sync (like `SmtpEmailAdapter`), built on `httpx.Client`. One sync client is held per adapter instance, reused across `send()` calls — `httpx.Client` is threadsafe for the same reasons as `boto3` (connection pool is internally locked).

Alternative considered: `requests`. Rejected — adds a second HTTP library to the project; `httpx` is already pulled in. `aiohttp` rejected for the same reason as `aioboto3` (sync adapters everywhere else).

### D6. Resend payload shape

The Resend API for "send email" is `POST /emails` with JSON body `{"from": "...", "to": ["..."], "subject": "...", "text": "...", "html": "..."}` and `Authorization: Bearer <api_key>`. The adapter renders the template via the same `EmailTemplateRegistry.render(...)` call the SMTP and console adapters use, then ships `text` only (HTML support is non-goal). Single `to` becomes a one-element list. Subject and body come straight from the rendered `EmailMessage`. The `from` address comes from `EmailSettings.resolved_from_address()`.

Failure modes:

| HTTP status | Port result |
| --- | --- |
| 2xx | `Ok(None)` |
| 4xx (any) | `Err(DeliveryError(reason=f"resend rejected: {status} {body['message']}"))` |
| 5xx (any) | `Err(DeliveryError(reason=f"resend transient error: {status}"))` |
| `httpx.HTTPError` (transport failure, timeout, etc.) | `Err(DeliveryError(reason=str(exc)))` |

No retry logic in the adapter. Callers that want retries enqueue the existing `send_email` background job (`background_jobs` already provides this affordance) and configure retries at the job layer. Keeping retry out of the adapter avoids accidentally double-sending on a non-idempotent provider API.

Alternative considered: in-adapter retry for 5xx + transport errors. Rejected — bottoms-up retries layer poorly; the job queue is the better seam.

### D7. Resend base URL configurable

`APP_EMAIL_RESEND_BASE_URL` defaults to `https://api.resend.com`. Operators can point it at a self-hosted compatible server (some teams run Resend's open-source MTA fork) or at a staging endpoint without touching code. Tests use `respx` to mount a transport on the default URL, so the env var only matters in real deployments.

### D8. Contract tests over integration tier

The S3 adapter is exercised by `moto` (an in-process `boto3` mock that the AWS testing ecosystem treats as canonical). `moto` runs in the same process, has no Docker requirement, and supports every S3 API the adapter calls. The adapter therefore stays in the existing `unit`-marker contract test rather than spawning a new integration tier. The Resend adapter is exercised by `respx`, which patches `httpx`'s transport — same rationale.

The existing `xfail(strict=True)` line for `_s3_factory` flips to a real parametrisation that constructs an S3 client pointed at `moto`'s in-process mock (`moto.mock_aws()` decorator or `@pytest.fixture` setup). The contract suite already separates `_REAL_ADAPTERS` (asserts behavior) from `_ALL_ADAPTERS` (just asserts the happy path); after this change there is no asymmetry — S3 joins `_REAL_ADAPTERS`.

Alternative considered: spin up a real LocalStack or MinIO testcontainer. Rejected — `moto` is faster, has no external dependencies, and covers the four operations the port exposes with full fidelity.

### D9. No `endpoint_url` in settings (yet)

Option to expose `APP_STORAGE_S3_ENDPOINT_URL` for R2/MinIO/self-hosted-S3 was considered. Not adding it in this change because (a) `boto3` already supports `AWS_ENDPOINT_URL_S3` and `AWS_ENDPOINT_URL` env vars natively at the SDK level, so operators pointing at R2 do not need a new template-specific setting, and (b) adding the field now expands the validator surface without a concrete use case. If a future change wants tighter coupling, it can promote the env var into `StorageSettings`.

### D10. Backwards compatibility

- The S3 adapter's constructor signature stays `(bucket: str, region: str)`. The `boto3` client is built internally; no external caller constructs the adapter anyway (composition root only).
- `EmailSettings.from_app_settings` keeps `backend in ("console", "smtp")` accepting and adds `"resend"` to both the literal and the validator. Existing callers that pass `console` or `smtp` see no change.
- `APP_EMAIL_BACKEND` accepts `resend` as a new value. The two new env vars are optional unless `backend == "resend"`.

## Risks / Trade-offs

- **boto3 install footprint** → `boto3` and its `botocore` dependency add ~25 MB to the image. Mitigation: it's a starter; operators who don't want AWS dependencies can fork and remove the adapter (and `boto3` from `pyproject.toml`) in 5 minutes. Document that path in `docs/file-storage.md`.
- **`moto` version drift vs `boto3`** → `moto` lags `boto3` API changes by weeks. Mitigation: pin `moto~=5.0` (latest as of writing) and bump deliberately. Contract tests will catch any incompatibility immediately.
- **Resend rate limits** → Free tier is 100 emails/day, 10/sec. A misconfigured loop in dev could exhaust the day's quota. Mitigation: keep `console` as the default in dev (`APP_EMAIL_BACKEND=console`), document the limit in `docs/email.md`.
- **API key in env** → standard 12-factor practice, but worth flagging. The settings validator does not log the key value, only `_RESEND_API_KEY missing` when validation fails. Mitigation: the existing pattern already used for `APP_AUTH_JWT_SECRET_KEY`.
- **Resend region: EU vs US** → Resend has separate EU and US data planes; same SDK shape but the base URL differs (`api.resend.com` US vs `api.eu.resend.com` EU). Mitigation: `APP_EMAIL_RESEND_BASE_URL` covers this without a code change.
- **Presigned URL preflight HEAD adds an extra call** → ~1 extra S3 round-trip per signing. Mitigation: signed URLs are not on a hot path; the trade gives contract parity with the local adapter, which is more valuable. If a consumer needs to skip the check, they can fork or we add an opt-out flag in a future change.
- **`httpx` promoted to runtime dep** → other features may start importing it inadvertently. Mitigation: the existing Import Linter contracts forbid the inbound-HTTP layer from importing arbitrary outbound dependencies; the Resend adapter imports `httpx` only inside `adapters/outbound/resend/`.

## Migration Plan

This change is additive at runtime. No data migrations, no schema changes, no breaking API changes for existing callers.

Rollout:
1. Merge with `APP_EMAIL_BACKEND` defaulting to `console` and `APP_STORAGE_ENABLED` defaulting to `false`. Existing deployments are unaffected.
2. Operators wanting Resend set `APP_EMAIL_BACKEND=resend`, `APP_EMAIL_RESEND_API_KEY=...`, and `APP_EMAIL_FROM=...`. Validate locally with `console` first, then flip.
3. Operators wanting S3 set `APP_STORAGE_ENABLED=true`, `APP_STORAGE_BACKEND=s3`, `APP_STORAGE_S3_BUCKET=...`, and provide AWS credentials via the standard `boto3` chain (env, instance profile, etc.).

Rollback: revert env vars to `console` / `local` (or `APP_STORAGE_ENABLED=false`). The adapter code stays in the tree without affecting runtime behavior.

## Open Questions

- Whether to keep `s3/README.md` after the stub is gone. Proposed disposition: trim it to "operator policy notes" — keep the IAM policy block and the bucket-configuration checklist (BPA, versioning, lifecycle, encryption) because that's reference material operators need, drop the "how to fill in the stub" section. Decided in tasks.md.
- Whether `Resend` should also accept `cc` and `bcc`. Decided no for this change — the port doesn't expose them, and adding them requires expanding `EmailPort.send` everywhere.
