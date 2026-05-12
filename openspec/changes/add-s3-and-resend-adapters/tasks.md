## 1. Dependencies

- [x] 1.1 Add `boto3~=1.34` to runtime `[project] dependencies` in `pyproject.toml`.
- [x] 1.2 Move `httpx>=0.28` from `[dependency-groups.dev]` into runtime `[project] dependencies` (keep the same version pin or tighten if needed).
- [x] 1.3 Add `moto~=5.0` and `respx~=0.21` to `[dependency-groups.dev]` in `pyproject.toml`.
- [x] 1.4 Run `uv lock` and `uv sync` to refresh the lockfile.

## 2. Settings — file_storage

- [x] 2.1 No new env vars for file_storage in this change (existing `APP_STORAGE_*` cover S3). Verify `AppSettings` fields `storage_backend`, `storage_s3_bucket`, `storage_s3_region` need no edits.
- [x] 2.2 Update the comment block around `storage_backend` in `src/platform/config/settings.py` to drop the "stub" language describing `s3`.

## 3. S3 adapter implementation

- [x] 3.1 Rewrite `src/features/file_storage/adapters/outbound/s3/adapter.py` as a real implementation: `__post_init__` builds `boto3.client("s3", region_name=self.region)`; methods call `put_object`, `get_object`, `delete_object`, `generate_presigned_url`; preserve the `@dataclass(slots=True)` shape and the `(bucket, region)` constructor signature.
- [x] 3.2 Implement error mapping: `ClientError.Error.Code in {"NoSuchKey", "404"}` → `ObjectNotFoundError(key=...)`; every other `ClientError` and `BotoCoreError` / `EndpointConnectionError` → `StorageBackendError(reason=str(exc))`.
- [x] 3.3 In `signed_url`, call `head_object` first and translate a 404/`NoSuchKey` to `ObjectNotFoundError` before signing. Clamp/reject `expires_in > 604800` with `StorageBackendError(reason="expires_in exceeds S3 maximum of 604800 seconds")`.
- [x] 3.4 Trim `src/features/file_storage/adapters/outbound/s3/README.md` down to operator-facing reference material only: keep the IAM policy block and the "Bucket configuration checklist". Drop the "Method ↔ boto3 mapping" and "Dependency" sections — those are now satisfied by the real implementation.
- [x] 3.5 If `__init__.py` re-exports the stub class, confirm the same name (`S3FileStorageAdapter`) is still exported.

## 4. S3 adapter tests

- [x] 4.1 In `src/features/file_storage/tests/contracts/test_file_storage_port_contract.py`, change `_s3_factory` to build an `S3FileStorageAdapter` against a `moto`-mocked S3 client (create the bucket inside the factory using `moto.mock_aws()`-decorated test or a `mock_aws` fixture).
- [x] 4.2 Remove the `xfail(strict=True)` wrapper around `_s3_factory` in both `_ALL_ADAPTERS` and the parametrisation note comment. Promote `_s3_factory` into `_REAL_ADAPTERS` so every contract scenario runs against S3.
- [x] 4.3 Add a unit test file `tests/unit/test_s3_adapter.py` (renamed from `test_s3_stub.py`) asserting the error-mapping edges and the `expires_in` guard.
- [x] 4.4 Run `make test-feature FEATURE=file_storage`; resolve failures until green.

## 5. Email — Resend adapter scaffold

- [x] 5.1 Create `src/features/email/adapters/outbound/resend/__init__.py` and `adapter.py`. Mirror the `SmtpEmailAdapter` shape: `@dataclass(slots=True)` with fields `registry: EmailTemplateRegistry`, `api_key: str`, `from_address: str`, `base_url: str = "https://api.resend.com"`, `timeout: float = 10.0`.
- [x] 5.2 In `__post_init__`, construct a long-lived `httpx.Client(base_url=self.base_url, timeout=self.timeout, headers={"Authorization": f"Bearer {self.api_key}"})` and store it on the instance. Keep the constructor parameter list minimal — the `httpx.Client` is internal.
- [x] 5.3 Implement `send(*, to, template_name, context)`: render via `self.registry.render(...)` (same try/except chain as the SMTP adapter for `UnknownTemplateError` and `TemplateRenderError`); short-circuit before HTTP if rendering fails.
- [x] 5.4 POST `{"from": self.from_address, "to": [to], "subject": message.subject, "text": message.body}` to `/emails`. Return `Ok(None)` on 2xx; `Err(DeliveryError(reason=f"resend rejected: {status} {message}"))` on 4xx (extract `message` from JSON body when present, fall back to `response.text`); `Err(DeliveryError(reason=f"resend transient error: {status}"))` on 5xx; `Err(DeliveryError(reason=str(exc)))` on `httpx.HTTPError`.
- [x] 5.5 Log success and failure with structured fields `event=email.resend.sent` / `event=email.resend.failed`, matching the SMTP adapter's logging shape.

## 6. Email settings + composition

- [x] 6.1 In `src/features/email/composition/settings.py`, change `EmailBackend = Literal["console", "smtp"]` to `Literal["console", "smtp", "resend"]`. Add fields `resend_api_key: str | None`, `resend_base_url: str` (default `"https://api.resend.com"`).
- [x] 6.2 Extend `EmailSettings.from_app_settings` to read `app.email_resend_api_key` and `app.email_resend_base_url`; widen the literal validator string to include `resend`.
- [x] 6.3 Extend `EmailSettings.validate(errors)`: when `backend == "resend"`, require `resend_api_key` and `from_address`; append missing-field messages naming `APP_EMAIL_RESEND_API_KEY` / `APP_EMAIL_FROM`.
- [x] 6.4 `EmailSettings.validate_production` keeps refusing `console` only; `resend` passes (subject to 6.3 already running first).
- [x] 6.5 In `src/platform/config/settings.py`, change `email_backend: Literal["console", "smtp"]` to `Literal["console", "smtp", "resend"]`. Add `email_resend_api_key: str | None = None` and `email_resend_base_url: str = "https://api.resend.com"` next to the existing SMTP fields, with a comment block matching the surrounding style.
- [x] 6.6 In `src/features/email/composition/container.py`, add a branch for `settings.backend == "resend"`: raise `RuntimeError("APP_EMAIL_RESEND_API_KEY is required when APP_EMAIL_BACKEND=resend")` if missing, then construct `ResendEmailAdapter(registry=..., api_key=..., from_address=settings.resolved_from_address(), base_url=settings.resend_base_url)`.
- [x] 6.7 Re-export `ResendEmailAdapter` from `src/features/email/adapters/outbound/resend/__init__.py`.

## 7. Email — Resend tests

- [x] 7.1 Add a `respx`-backed factory `_resend_factory(registry)` to `src/features/email/tests/contracts/test_email_port_contract.py`. Wrap the existing `test_valid_send_returns_ok` parametrisation to include the new factory; install a respx route at `https://api.resend.com/emails` returning HTTP 200.
- [x] 7.2 Add `tests/unit/test_resend_adapter.py` covering: 422 with `{"message": "..."}` → `DeliveryError(reason)` containing `"422"` and the message; 503 → `DeliveryError(reason)` with `"503"`; `httpx.ConnectError` raised by the mocked transport → `DeliveryError(reason=str(exc))`; unknown template short-circuits with no HTTP request.
- [x] 7.3 Custom-`base_url` assertion folded into `test_resend_adapter.py` rather than a separate file (kept the test count tight).
- [x] 7.4 Run `make test-feature FEATURE=email`; resolve failures until green.

## 8. Documentation

- [x] 8.1 Update `docs/file-storage.md`: rewrite the "S3 stub" section as "S3" (real). Add a short "AWS setup" subsection pointing at the trimmed IAM/bucket-policy notes in `adapters/outbound/s3/README.md`. Add a note about `AWS_ENDPOINT_URL_S3` for R2/MinIO operators.
- [x] 8.2 Update `docs/email.md`: add a "Resend" subsection (env vars, API key acquisition, base URL override, free-tier rate-limit warning). Update the env-var table at the top.
- [x] 8.3 Update `docs/operations.md` env-var reference for the new `APP_EMAIL_RESEND_*` variables and any changed defaults.
- [x] 8.4 Update `CLAUDE.md`: the file_storage row in the feature table (drop "stub" wording for S3), the email row (`console + SMTP + Resend adapters`), the "Key env vars (infrastructure)" table, and the "Production checklist" subsection.
- [x] 8.5 Update `.env.example` with the new email/SMTP/Resend block (previous file only had file-storage entries; the email defaults were implicit).

## 9. Verification

- [x] 9.1 Run `make quality` (lint + arch lint + typecheck); resolve violations.
- [x] 9.2 Run `make test`; ensure all unit and e2e suites pass — 295 passed, 13 deselected.
- [x] 9.3 Run `make cov` to confirm coverage gate (≥80%) — total coverage 88.59%.
- [x] 9.4 Run `openspec validate add-s3-and-resend-adapters --strict` and resolve any structural issues before archival.
