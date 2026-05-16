# Tasks — remove-s3-stub

> NOTE: The ROADMAP/brief calls this a "stub raising `NotImplementedError`".
> That is wrong — `S3FileStorageAdapter` is a real, fully-tested `boto3`
> adapter (see `proposal.md` → "Correction to the ROADMAP/brief framing").
> This is steps-3/4-class work (real backend + selector + validator +
> extra + contract suite), NOT step-6-class (dead-code) work.

## 1. Delete the S3 adapter package

- [ ] Delete `src/features/file_storage/adapters/outbound/s3/adapter.py`
- [ ] Delete `src/features/file_storage/adapters/outbound/s3/__init__.py`
- [ ] Delete `src/features/file_storage/adapters/outbound/s3/README.md`
- [ ] Delete the now-empty
      `src/features/file_storage/adapters/outbound/s3/` directory
      (including any `__pycache__`)

## 2. Settings surface

- [ ] In `src/app_platform/config/settings.py`: narrow
      `storage_backend` to `Literal["local"]`; remove
      `storage_s3_bucket` and `storage_s3_region`; remove the S3 lines
      from the File-storage comment block; reword the `local`/`s3`
      description comment so it states `local` is the only backend and
      production has no file-storage transport until the real AWS S3
      adapter (a later roadmap step — do NOT hard-code a step number).
      Keep `storage_enabled` and `storage_local_path`.
- [ ] In `src/features/file_storage/composition/settings.py`: narrow
      `StorageBackend` to `Literal["local"]`; remove the `s3_bucket`
      and `s3_region` dataclass fields; remove the `s3_bucket`/
      `s3_region` keyword params from `from_app_settings`; remove the
      two `app.storage_s3_*` assignments in the `if app is not None:`
      branch; narrow the `backend not in ("local", "s3")` guard and its
      error message to `("local",)` / names only `'local'`; delete the
      `if self.backend == "s3":` block in `validate()`; reword
      `validate_production` so it still appends an error when
      `self.enabled and self.backend == "local"` but the message no
      longer names `s3` / `APP_STORAGE_S3_BUCKET` (state no production
      file-storage backend exists yet — the real AWS S3 adapter arrives
      at a later roadmap step). **The reworded message MUST retain the
      literal substring `APP_STORAGE_BACKEND`** so the shared baseline
      test's `match="APP_STORAGE_BACKEND"` still resolves.

## 3. Composition

- [ ] In `src/features/file_storage/composition/container.py`: remove
      the entire `elif settings.backend == "s3":` arm (the
      `s3_bucket` guard, the deferred
      `from features.file_storage.adapters.outbound.s3 import
      S3FileStorageAdapter`, the `boto3`-missing `RuntimeError`, adapter
      construction); remove the module-level `boto3`/`s3`-extra comment
      block. The trailing
      `else: raise RuntimeError(f"Unknown storage backend: …")` guard
      stays (mark `# pragma: no cover` — `StorageSettings` construction
      now guarantees `local`); `local` is the only remaining branch
- [ ] Audited & confirmed — **no edit** to `src/main.py`,
      `src/worker.py`, or `src/cli/create_super_admin.py`: none pass any
      `s3_*` kwarg to `StorageSettings.from_app_settings` (verify with a
      grep during implementation; the only `storage_s3_*` references are
      inside `StorageSettings.from_app_settings` itself and
      `AppSettings`)

## 4. Docstring / comment rewording (no behaviour change)

- [ ] `src/features/file_storage/__init__.py`: drop the
      "``s3`` as a stub for production integration" clause — and fix
      the pre-existing inaccuracy (it called the real adapter a stub).
      State it ships a port, a `local` (dev/test) adapter, and a fake.
- [ ] `src/features/file_storage/application/ports/file_storage_port.py`:
      reword the module docstring "(local filesystem, S3, GCS, …)" and
      the per-method "S3 …" asides (`put` content-type, `signed_url`
      presigned-URL note) to be backend-neutral or drop the S3 example;
      the four method signatures and the contract are unchanged
- [ ] `src/features/file_storage/application/errors.py`: reword the
      `StorageBackendError` docstring "(IO error, S3 5xx, etc.)" to be
      backend-neutral
- [ ] `src/features/file_storage/adapters/outbound/local/adapter.py`:
      grep for an "S3"-naming aside; reword backend-neutral **only if**
      it specifically names the removed backend (no behaviour change).
      If it has no such reference, no edit
- [ ] `src/features/file_storage/tests/fakes/fake_file_storage.py`:
      audited — no S3 naming; **no change**

## 5. Config files and tooling

- [ ] In `.env.example`: remove `APP_STORAGE_S3_BUCKET` and
      `APP_STORAGE_S3_REGION`; reword the
      `# Set APP_STORAGE_ENABLED=true to opt in (production then
      requires 's3').` comment so it no longer names `s3` (state
      `local` is the only backend; production file storage arrives with
      the real AWS S3 adapter at a later roadmap step). Keep
      `APP_STORAGE_ENABLED`, `APP_STORAGE_BACKEND`,
      `APP_STORAGE_LOCAL_PATH`
- [ ] In `pyproject.toml`: remove the `s3 = ["boto3~=1.34"]` extra and
      its `# S3 file-storage adapter. …` comment block; remove the
      `#   uv sync --extra s3           # S3 file-storage adapter`
      install-modes comment line; remove the `dev`-group `"boto3~=1.34",`,
      `"moto~=5.0",`, and `"boto3-stubs[s3]>=1.34",` entries (boto3
      audit: no `src/` code imports `boto3`/`botocore`/`moto` after this
      change). **Do NOT touch** `renovate.json` or the
      `quality-automation` "Co-versioned package groups are declared"
      scenario's `boto3 + botocore` group (inert with boto3 absent;
      re-touching pre-empts the AWS-S3 naming decision). There is **no**
      `boto3` Import Linter `forbidden_modules` entry to keep or remove
      (verified — nothing to do on that axis)
- [ ] Run `uv lock` so `uv.lock` drops `boto3`/`botocore`/`moto`/
      `boto3-stubs` and any transitive deps now unused. Commit the
      regenerated lock

## 6. Tests

- [ ] Delete `src/features/file_storage/tests/unit/test_s3_adapter.py`
- [ ] In
      `src/features/file_storage/tests/contracts/test_file_storage_port_contract.py`:
      remove `import boto3`, `from moto import mock_aws`, the
      `from features.file_storage.adapters.outbound.s3 import
      S3FileStorageAdapter` import, the `_S3_TEST_BUCKET`/
      `_S3_TEST_REGION` constants, the `_aws_mock` autouse fixture, the
      `_s3_factory` function, and the `s3` parametrisation id /
      `_s3_factory` entry; keep the `_fake_factory` and `_local_factory`
      factories and all their scenarios. Reword the module docstring so
      it no longer says "the S3 adapter (backed by `moto`)"
- [ ] In `src/features/file_storage/tests/unit/test_settings.py`:
      delete `test_s3_backend_requires_bucket`; in
      `test_unknown_backend_rejected` drop the now-removed
      `s3_bucket=None`/`s3_region="us-east-1"` kwargs (keep the
      `backend="gcs"` → `ValueError` assertion); in
      `test_local_backend_requires_path` drop the
      `s3_bucket=None`/`s3_region="us-east-1"` kwargs. Keep the
      local-path guard assertion
- [ ] `src/app_platform/tests/test_settings.py`: **no change.**
      Audited — `_VALID_PROD_ENV` sets no `APP_STORAGE_*` key, so the
      storage refusal is NOT always-present;
      `_assert_only_always_present_refusals` stays at exactly two
      entries (email + jobs) and its `len(bullets) == 2` is unchanged.
      `test_production_rejects_local_storage_enabled` is kept unchanged
      and still resolves via the retained `APP_STORAGE_BACKEND`
      substring in the reworded validator message (confirm the substring
      is present during implementation)

## 7. Docs (S3 lines only — no wholesale rewrite)

- [ ] `docs/file-storage.md`: drop the "S3 adapter" At-A-Glance row,
      the `APP_STORAGE_S3_BUCKET`/`APP_STORAGE_S3_REGION` config rows,
      the entire `### S3 (S3FileStorageAdapter)` / `#### Pointing at R2
      / MinIO …` / `#### AWS setup` subsections, and the `s3` arm of
      "Contract Tests" + the `APP_STORAGE_BACKEND` `s3` note; restate
      the intro as "ships with a port, one adapter (`local`, dev/test),
      and a fake"; state production file storage arrives with the real
      AWS S3 adapter at a later roadmap step. Keep the "Extending The
      Feature → Add a different cloud" generic guidance; drop only the
      clause asserting the S3 adapter ships
- [ ] `docs/operations.md`: drop the `uv sync --extra s3` install-modes
      row, the `APP_STORAGE_BACKEND=s3 without --extra s3 → boto3 …`
      example bullet, the `APP_STORAGE_S3_BUCKET`/`APP_STORAGE_S3_REGION`
      env-reference rows, and the `s3` clause of the
      `APP_STORAGE_BACKEND` row; replace with the minimal accurate
      post-removal reality (`APP_STORAGE_BACKEND` accepts only `local`;
      production has no file-storage backend until the real AWS S3
      adapter). Reword the readiness-probe `head_bucket` line so it no
      longer asserts an S3 readiness check. Do NOT rewrite the broader
      "production refuses to start if…" narrative (ROADMAP step 11)
- [ ] `docs/architecture.md`: feature-table row → drop the S3-stub
      clause (and the inaccuracy); the "Object storage …
      `APP_STORAGE_BACKEND=s3` (production)" row → state production file
      storage arrives with the real AWS S3 adapter at a later roadmap
      step; remove the `S3 stub | The adapter raises NotImplementedError
      …` row and the "The S3 file-storage adapter is a stub. Filling it
      in requires `boto3` …" sentence
- [ ] `docs/observability.md`: remove/neutralise the
      `head_bucket against S3 when APP_STORAGE_ENABLED=true and
      APP_STORAGE_BACKEND=s3` readiness bullet
- [ ] `docs/development.md`: remove the dependency-group table row
      `| boto3 | boto3, botocore, boto3-stubs, moto |`
- [ ] `README.md`: docs-link "local/S3" → "local"; feature-table row
      "`FileStoragePort` plus `local` adapter and `s3` stub." →
      "`FileStoragePort` plus the `local` adapter (dev/test)"; tree
      comment `# FileStoragePort, local/S3 adapters` → `local adapter`
- [ ] `CLAUDE.md`: feature-table row
      `| file_storage | FileStoragePort, local + S3 (boto3) adapters |`
      → `local adapter (dev/test); production file storage arrives with
      the real AWS S3 adapter at a later roadmap step`; remove the
      File-storage section's `adapters/outbound/s3/ — stub; raises
      NotImplementedError` bullet; reword the Production-checklist
      bullet `APP_STORAGE_ENABLED=true with APP_STORAGE_BACKEND=local`
      to state `local` is the only backend / production file storage
      not yet available (real AWS S3 adapter at a later roadmap step);
      drop the `APP_STORAGE_BACKEND` key-env-var row's `s3 in
      production` note (state `local` only)
- [x] `CONTRIBUTING.md`: line-by-line audit — only generic references
      (feature-name list, doc-link). **Zero** S3-adapter/S3-stub/
      `boto3`/`APP_STORAGE_S3_*` references. **No change.**
- [x] `docs/background-jobs.md`: audited — **no S3 reference**. **No
      change** (despite the brief listing it as in scope)

## 8. Verify

- [ ] `make lint-arch` — no new import-linter violation involving
      `src.features.file_storage`
- [ ] `make quality` green (lint + arch + typecheck)
- [ ] `make test` green; specifically the file-storage contract suite
      passes for `fake` and `local`, and
      `test_production_rejects_local_storage_enabled` still passes
- [ ] `grep -rin 's3\|boto3\|botocore\|moto\|S3FileStorage\|
      APP_STORAGE_S3' src docs *.md .env.example pyproject.toml` returns
      no S3-adapter / S3-backend hit other than the deliberately-kept
      Renovate `boto3 + botocore` group and the generic
      feature-name/doc-link mentions in `CONTRIBUTING.md`/`README.md`
- [ ] `openspec validate remove-s3-stub --strict` passes
