## Why

ROADMAP ETAPA I step 7 ("dejar el repo honesto"): remove the non-`local`
production-shaped file-storage backend and every config/test/doc/spec
surface that promises it. The ROADMAP decision (line 26) is explicit:
remove non-AWS production-shaped adapters one at a time; steps 3–6
already deleted SMTP, Resend, arq, and the SpiceDB stub. This is the
file-storage step. The real AWS file-storage adapter (`aws_s3`) arrives
at a later roadmap step (the SecretsPort work and the real AWS S3
adapter are sequenced after ETAPA I); production file storage is
intentionally not bootable until then.

### Correction to the ROADMAP/brief framing — the S3 adapter is NOT a `NotImplementedError` stub

ROADMAP.md line 48 and the change brief describe step 7 as "eliminar
stub S3 que levanta `NotImplementedError`" and frame it as mirroring the
step-6 SpiceDB stub. **That premise is factually wrong against the
current code and the canonical spec.** Verified directly:

- `src/features/file_storage/adapters/outbound/s3/adapter.py` is a
  **fully implemented, runnable** `boto3`-backed `FileStoragePort`:
  real `put`/`get`/`delete`/`list`/`signed_url`, presigned-URL
  generation with the 7-day SigV4 guard, `ClientError`/`BotoCoreError`
  mapping to `ObjectNotFoundError`/`StorageBackendError`, and a
  pool-sized `botocore` client. **No method raises
  `NotImplementedError`.** (Contrast: `docs/architecture.md:245` and
  `src/features/file_storage/__init__.py` carry stale "stub /
  `NotImplementedError`" wording that the code already contradicts —
  in-tree drift, not the truth.)
- It is exercised by a real test suite: the shared `FileStoragePort`
  contract is parametrised three ways (`fake`, `local`, `s3`) with the
  `s3` arm driven by `moto`'s in-process AWS mock, plus an 8-test
  dedicated unit suite (`test_s3_adapter.py`) covering error-mapping
  edges.
- It carries real dependencies: the `s3 = ["boto3~=1.34"]`
  optional-dependency extra, and `boto3~=1.34` + `moto~=5.0` +
  `boto3-stubs[s3]>=1.34` in the `dev` dependency group.
- The canonical `file-storage` capability spec
  (`openspec/specs/file-storage/spec.md`) contains a requirement named
  exactly **`S3 adapter is a real boto3 implementation`** that mandates
  it "SHALL NOT raise `NotImplementedError`" and "SHALL pass the same
  behavioural contract as the local adapter and the in-memory fake".

So step 7 is **not** a trivial dead-code deletion like step 6 (SpiceDB).
It is the same class of work as steps 3/4 (SMTP/Resend) — a real,
selectable, production-shaped backend with a backend selector, settings,
a production validator arm, a dependency extra, and a parametrised
contract suite — and it must follow the steps-3/4 precedent, not the
step-6 one. The backend is removed because the ROADMAP is removing
non-AWS production-shaped adapters and re-introducing the real one as an
explicitly AWS-shaped `aws_s3` adapter at a later step; the current
implementation no longer pays its way:

1. **It carries a full real adapter, a dependency extra, a test mock,
   and a config surface for a path the roadmap is replacing.**
   `S3FileStorageAdapter` (`__init__.py`, `adapter.py`) plus a 66-line
   `README.md` of AWS IAM/bucket guidance; the `s3` extra and the
   `boto3`/`moto`/`boto3-stubs` dev deps; two `storage_s3_*` fields plus
   a comment block on `AppSettings`; the matching `s3_bucket`/`s3_region`
   projection on `StorageSettings` (fields, the `from_app_settings`
   kwargs and `app.storage_s3_*` assignments, the
   `backend not in ("local","s3")` guard, the `if self.backend == "s3"`
   `validate()` arm); the `s3` arm of `build_file_storage_container`
   with its deferred `boto3`-missing import guard; the three-way
   contract parametrisation and the standalone S3 unit suite.
2. **It widens the public config contract with knobs the roadmap is
   re-shaping.** `.env.example` ships `APP_STORAGE_S3_BUCKET` /
   `APP_STORAGE_S3_REGION`; `docs/file-storage.md`, `docs/operations.md`,
   `docs/architecture.md`, `docs/observability.md`, `README.md`, and
   `CLAUDE.md` document the S3 env vars, the `s3` install extra, R2/MinIO
   endpoint overrides, and an AWS IAM-policy workflow. A reader cannot
   tell the current S3 path is being retired ahead of the AWS-shaped
   adapter.
3. **`storage_backend` collapses to a single value.** With the `s3`
   backend gone, `Literal["local", "s3"]` becomes `Literal["local"]` —
   `local` is the only backend. Every multi-backend branch
   (`build_file_storage_container`'s `elif`, the `from_app_settings`
   guard listing two names, the `validate()` `s3` arm, the contract
   suite's three-way parametrisation) is now a degenerate one-arm
   dispatch carrying a dead alternative.

This step deletes the current S3 backend only. `local` (the dev/test
adapter) is unchanged and remains the sole adapter. `FileStoragePort`
and `FakeFileStorage` are unchanged. The real AWS file-storage adapter
(`aws_s3`) and any AWS/`boto3` code or config are a later roadmap step
and are explicitly out of scope here.

### Key decision — the production file-storage validator stays a refusal

Removing the S3 backend leaves `local` as the only `storage_backend`
value. The file-storage production validator currently refuses `local`
when `APP_ENVIRONMENT=production` **and** `APP_STORAGE_ENABLED=true`
(`src/features/file_storage/composition/settings.py`,
`validate_production`). After this step there is **no production-capable
file-storage backend at all** until the real `aws_s3` adapter is added
at a later roadmap step.

**Decision: keep the refusal honest — the validator SHALL continue to
refuse `local` in production when storage is enabled.** This mirrors the
established steps-3/4 precedent (email/jobs) exactly. Production-with-
file-storage is intentionally not bootable until the AWS adapter
arrives. This is the correct, honest state of an AWS-first starter
mid-cleanup:

- **Safety invariant preserved.** The refusal exists so production never
  silently runs file storage on a per-pod local disk: multi-replica
  deploys would write a blob on one node and 404 it from another, and a
  pod restart would lose data. That risk does not disappear because
  `local` became the only value; it gets *worse* (no safe alternative to
  fall back to). Relaxing the refusal so production boots on `local`
  would silently weaken production safety: a real deploy would come up
  "green" while blobs are scattered across ephemeral pod disks. An
  explicit boot failure with a clear message is strictly safer.
- **Honest over convenient.** The ROADMAP norte is "una sola opción
  opinada > tres opciones a medias" and "dejar el repo honesto". The
  honest statement after step 7 is: *this starter has no production
  file-storage transport yet; it arrives with the real `aws_s3` adapter
  at a later roadmap step*. A validator that refuses to boot says exactly
  that. One that accepts `local` in production would lie. **The
  `APP_STORAGE_ENABLED` escape hatch is unchanged**: projects that never
  wire `FileStoragePort` leave `APP_STORAGE_ENABLED=false` and are not
  forced to set anything up — the refusal only fires when storage is
  actually used.
- **Minimal blast radius, no roadmap pre-emption.** Keeping the refusal
  means the only code change it forces is wording: the message currently
  says "configure 's3' and set `APP_STORAGE_S3_BUCKET`"; the `s3`
  backend no longer exists, so the message must stop naming it. The
  honest replacement states that no production file-storage backend
  exists yet and points at the later roadmap step (the real AWS S3
  adapter), without hard-coding a step number. This does **not**
  pre-empt the `docs/operations.md` "production refuses to start if…"
  narrative rewrite (ROADMAP step 11) or the real `aws_s3` adapter and
  its accept-path (a later roadmap step). It is the minimum the S3
  removal forces for code/test/spec coherence.

Considered and rejected: *relax the refusal so production may boot on
`local`.* Rejected because it converts a loud, intentional "not ready
yet" into a silent split-brain blob store in production — the exact
failure the validator exists to prevent. The temporary inability to
boot a production deployment *with file storage* is not a regression
introduced here; it is the truthful consequence of removing the last
non-AWS production backend before the AWS one lands, and it is
recoverable the moment the real `aws_s3` adapter ships.

### Shared production-baseline test — storage is NOT an always-present refusal (audited)

Steps 3–5 had to repoint the shared `_VALID_PROD_ENV` baseline in
`src/app_platform/tests/test_settings.py` (and grow
`_assert_only_always_present_refusals`) because the email and jobs
refusals became unconditionally present in any production env. **This
step does not.** Audited: `_VALID_PROD_ENV` does **not** set any
`APP_STORAGE_*` key, so the baseline inherits `storage_enabled=False`
(the `AppSettings` default), and the file-storage validator only fires
when `APP_STORAGE_ENABLED=true`. The storage refusal is therefore **not
always-present**. Consequences, all verified against the current test:

- `_VALID_PROD_ENV` needs **no `APP_STORAGE_*` change** (it sets none).
- `_assert_only_always_present_refusals` stays at exactly **two**
  always-present refusals (email-backend + jobs-backend). It does **not**
  gain a third entry, and its `len(bullets) == 2` assertion is unchanged.
- `test_production_rejects_local_storage_enabled` already opts the
  storage axis in explicitly (`APP_STORAGE_ENABLED=true` +
  `APP_STORAGE_BACKEND=local`) and asserts `match="APP_STORAGE_BACKEND"`.
  It stays valid **iff** the reworded validator message still contains
  the literal substring `APP_STORAGE_BACKEND`. The reworded message MUST
  retain that substring (it does — it still leads with
  `APP_STORAGE_BACKEND must not be 'local' in production …`); only the
  trailing `configure 's3' and set APP_STORAGE_S3_BUCKET` clause is
  replaced with backend-neutral wording. No other `_VALID_PROD_ENV`-based
  test references storage.

## What Changes

- Delete the S3 adapter package
  `src/features/file_storage/adapters/outbound/s3/`
  (`__init__.py`, `adapter.py`, `README.md`).
- Narrow `storage_backend` from `Literal["local", "s3"]` to
  `Literal["local"]`; remove the `storage_s3_bucket` and
  `storage_s3_region` fields and the S3 lines from the File-storage
  comment block on `AppSettings`
  (`src/app_platform/config/settings.py`). Reword the
  `local`/`s3` description comment to state `local` is the only backend
  and production has no file-storage transport until the real AWS S3
  adapter (a later roadmap step). Keep `storage_enabled` and
  `storage_local_path`.
- In `src/features/file_storage/composition/settings.py`: narrow
  `StorageBackend` to `Literal["local"]`; remove the `s3_bucket` and
  `s3_region` dataclass fields; remove the `s3_bucket`/`s3_region`
  `from_app_settings` keyword params and the two `app.storage_s3_*`
  assignments in the `app is not None` branch; narrow the
  `backend not in ("local", "s3")` guard and its message to
  `("local",)` / names only `'local'`; remove the
  `if self.backend == "s3"` arm from `validate()`; reword
  `validate_production` so it still appends an error when
  `enabled and backend == "local"` but the message no longer names `s3`
  / `APP_STORAGE_S3_BUCKET` — it states no production file-storage
  backend exists yet (the real AWS S3 adapter arrives at a later roadmap
  step) **while keeping the literal substring `APP_STORAGE_BACKEND` so
  the shared baseline test's `match=` still resolves**.
- In `src/features/file_storage/composition/container.py`: remove the
  entire `elif settings.backend == "s3":` arm (bucket guard, deferred
  `from features.file_storage.adapters.outbound.s3 import
  S3FileStorageAdapter`, the `boto3`-missing `RuntimeError`, adapter
  construction) and the module-level `boto3`/`s3`-extra comment block;
  `local` becomes the only branch. Keep the trailing
  `else: raise RuntimeError(f"Unknown storage backend: …")` defensive
  arm (now `# pragma: no cover` since `StorageSettings` construction
  guarantees `local`).
- Reword S3-stub/-backend-naming docstrings/comments **only** (no
  behaviour change): `src/features/file_storage/__init__.py` (drop the
  "`s3` as a stub for production integration" clause — and fix the
  pre-existing inaccuracy: it called the real adapter a stub),
  `src/features/file_storage/application/ports/file_storage_port.py`
  (the module docstring "(local filesystem, S3, GCS, …)" and the two
  per-method "S3 …" asides become backend-neutral or drop the S3
  example), `src/features/file_storage/application/errors.py`
  (`StorageBackendError` docstring "(IO error, S3 5xx, etc.)" →
  backend-neutral), `src/features/file_storage/adapters/outbound/local/`
  adapter (any "S3" comparison aside reworded backend-neutral if
  present — verify; only reword if it specifically names the removed
  backend). `src/features/file_storage/tests/fakes/fake_file_storage.py`
  has no S3 naming (audited — no change).
- Remove `APP_STORAGE_S3_BUCKET` and `APP_STORAGE_S3_REGION` and reword
  the `# Set APP_STORAGE_ENABLED=true … (production then requires 's3')`
  comment in `.env.example` so it no longer names `s3` (state `local` is
  the only backend; production file storage arrives with the real AWS S3
  adapter at a later roadmap step). `APP_STORAGE_ENABLED` /
  `APP_STORAGE_BACKEND` / `APP_STORAGE_LOCAL_PATH` stay.
- In `pyproject.toml`: remove the `s3 = ["boto3~=1.34"]` extra and its
  three-line comment block, and the `#   uv sync --extra s3 …`
  install-modes comment line; remove the `dev`-group `"boto3~=1.34"`,
  `"moto~=5.0"`, and `"boto3-stubs[s3]>=1.34"` entries (boto3 audit
  below: after this change no `src/` code imports `boto3`/`botocore`/
  `moto`). **Leave the Renovate `boto3` + `botocore` package group in
  `renovate.json` and its `quality-automation` "Co-versioned package
  groups are declared" spec scenario UNTOUCHED** — it is inert with
  boto3 absent and re-touching it would pre-empt the AWS-S3-adapter
  naming decision (same posture step 5 took with the `arq + redis`
  Renovate group). This omission is called out explicitly. `uv lock`
  MUST be regenerated after the `pyproject.toml` edits.
- Delete `src/features/file_storage/tests/unit/test_s3_adapter.py` (the
  only dedicated test of the deleted adapter).
- De-parametrise
  `src/features/file_storage/tests/contracts/test_file_storage_port_contract.py`:
  drop `import boto3`, `from moto import mock_aws`, the
  `from features.file_storage.adapters.outbound.s3 import
  S3FileStorageAdapter` import, the `_aws_mock` autouse fixture, the
  `_S3_TEST_BUCKET`/`_S3_TEST_REGION` constants, the `_s3_factory`, and
  the `s3` parametrisation id; keep `fake` and `local`. Reword the
  module docstring so it no longer says "the S3 adapter (backed by
  `moto`)".
- In `src/features/file_storage/tests/unit/test_settings.py`: delete
  `test_s3_backend_requires_bucket`; in `test_unknown_backend_rejected`
  drop the now-removed `s3_bucket=`/`s3_region=` kwargs (keep the
  `backend="gcs"` rejection assertion); in `test_local_backend_requires_path`
  drop the `s3_bucket=`/`s3_region=` kwargs. Keep the local-path guard
  test.
- In `src/app_platform/tests/test_settings.py`: **no `_VALID_PROD_ENV`
  change and no `_assert_only_always_present_refusals` change** (storage
  is disabled in the baseline — audited above).
  `test_production_rejects_local_storage_enabled` is **kept unchanged**
  in structure; it continues to assert
  `pytest.raises(ValidationError, match="APP_STORAGE_BACKEND")`, which
  resolves because the reworded validator message retains the
  `APP_STORAGE_BACKEND` substring. (Confirm during implementation that
  the reworded message still contains `APP_STORAGE_BACKEND`; if a future
  reviewer prefers asserting the new backend-neutral phrasing, the test
  may be tightened, but the minimal change leaves it as-is.)
- Remove the S3 lines **only** from docs (no wholesale rewrite —
  ROADMAP steps 9/10 own README/CLAUDE re-framing; step 11 owns the
  `docs/operations.md` "production refuses to start if…" narrative):
  - `docs/file-storage.md`: drop the "S3 adapter" At-A-Glance row, the
    `APP_STORAGE_S3_BUCKET`/`APP_STORAGE_S3_REGION` config rows, the
    entire `### S3 (S3FileStorageAdapter)` / `#### Pointing at R2 /
    MinIO …` / `#### AWS setup` subsections, and the `s3` arm of the
    "Contract Tests" list and the `APP_STORAGE_BACKEND` `s3` note;
    restate the intro as "ships with a port, one adapter (`local`,
    dev/test), and a fake"; state production file storage arrives with
    the real AWS S3 adapter at a later roadmap step. Leave the
    "Extending The Feature → Add a different cloud" guidance (it teaches
    the port-implementation pattern generically, not the deleted
    adapter) but drop any clause that says the S3 adapter ships.
  - `docs/operations.md`: drop the `uv sync --extra s3` install-modes
    row, the `APP_STORAGE_BACKEND=s3 without --extra s3 → boto3 …`
    missing-extra example bullet, the `APP_STORAGE_S3_BUCKET` /
    `APP_STORAGE_S3_REGION` env-reference rows, and the `s3` clause of
    the `APP_STORAGE_BACKEND` row; replace with the minimal accurate
    post-removal reality (`APP_STORAGE_BACKEND` accepts only `local`;
    production has no file-storage backend until the real AWS S3
    adapter). Reword the readiness-probe `head_bucket` line so it no
    longer asserts an S3 readiness check (file storage has no remote
    backend to probe now) — minimal factual correction, not the
    narrative rewrite (step 11 owns that). Do **not** rewrite the
    broader "production refuses to start if…" narrative.
  - `docs/architecture.md`: feature-table row `file_storage |
    FileStoragePort, local adapter, S3 stub.` → drop the S3-stub clause
    (and fix the inaccuracy — it was never a stub); the
    "Object storage … `APP_STORAGE_BACKEND=s3` (production)" row →
    state production file storage arrives with the real AWS S3 adapter
    at a later roadmap step; remove the `S3 stub | The adapter raises
    NotImplementedError …` table row (factually wrong *and* removed);
    remove the "The S3 file-storage adapter is a stub. Filling it in
    requires `boto3` …" sentence.
  - `docs/observability.md`: remove/neutralise the `head_bucket against
    S3 when APP_STORAGE_ENABLED=true and APP_STORAGE_BACKEND=s3`
    readiness bullet — there is no S3 backend to probe post-removal.
  - `docs/development.md`: the dependency-group table row
    `| boto3 | boto3, botocore, boto3-stubs, moto |` is removed (those
    deps go with this change).
  - `README.md`: docs-link "local/S3" → "local"; feature-table row
    "`FileStoragePort` plus `local` adapter and `s3` stub." →
    "`FileStoragePort` plus the `local` adapter (dev/test)"; tree
    comment `# FileStoragePort, local/S3 adapters` → `local adapter`.
  - `CLAUDE.md`: feature-table row `| file_storage | FileStoragePort,
    local + S3 (boto3) adapters |` → `local adapter (dev/test);
    production file storage arrives with the real AWS S3 adapter at a
    later roadmap step`; the File-storage section's
    `adapters/outbound/s3/ — stub; raises NotImplementedError` bullet is
    removed; the Production-checklist bullet
    `APP_STORAGE_ENABLED=true with APP_STORAGE_BACKEND=local` is reworded
    to state `local` is the only backend and production file storage is
    not yet available (real AWS S3 adapter at a later roadmap step);
    remove the `APP_STORAGE_BACKEND` key-env-var row's `s3 in
    production` note (state `local` only); the `background-jobs.md`
    doc has no S3 reference (audited — no change despite the brief
    listing it).
  - `CONTRIBUTING.md`: **no change.** A line-by-line audit found only
    generic references (the feature-name enumeration and the
    `docs/file-storage.md` doc-link) — **zero** S3-adapter / S3-stub /
    `boto3` / `APP_STORAGE_S3_*` references that the removal
    invalidates. This is called out explicitly because the step-4
    (Resend) audit initially missed real `CONTRIBUTING.md` references;
    this time the file genuinely has none.

**Production-validator coherence (required by the constraint):** the
file-storage production validator continues to refuse `local` in
production when `APP_STORAGE_ENABLED=true` (see "Key decision"). The only
forced change is its message no longer naming the removed `s3` backend /
`APP_STORAGE_S3_BUCKET`; it now states no production file-storage
transport exists yet, while retaining the `APP_STORAGE_BACKEND`
substring so the shared baseline test still resolves. This does not
pre-empt ROADMAP step 11 (operations.md narrative) or the later roadmap
step that adds the real `aws_s3` adapter and its accept-path.

**Capabilities — Modified**
- `file-storage`: the `S3 adapter is a real boto3 implementation`
  requirement is removed entirely (REMOVED). `FileStoragePort contract`,
  `Local adapter remains the development default`, and `Settings select
  the active adapter` no longer enumerate `s3`/`boto3` and reflect
  `local` as the only backend with no production transport. `Adapters
  are isolated from inbound layers` is restated to drop the deleted S3
  module from its scope wording (the import-linter guarantee is
  unchanged).
- `project-layout`: `S3 adapter is configured for FastAPI concurrency`
  is removed entirely (REMOVED) — it is wholly about the deleted boto3
  client. `Documentation reflects the new layout` is restated so its
  "the file-storage S3 'ships as scaffolding' stub note … SHALL remain"
  carve-out no longer references a deleted S3 stub (the
  scaffold-recovery restriction itself is unchanged).
- `quality-automation`: `Runtime dependencies are split into core, api,
  worker, and adapter extras` no longer lists an `s3` extra, a `boto3`
  dependency, or an `s3`-extra missing-startup-error scenario. `Integration
  markers reflect real-backend usage` is restated so its "(real …
  S3 via testcontainers or moto)" parenthetical no longer names the
  removed S3/moto path.
- `authentication`: `Every documented production refusal has a unit
  test` is restated so the storage-backend refusal it implies is "no
  production file-storage backend exists" rather than "configure 's3'".

**Capabilities — New**
- None.

## Impact

- **Deleted package**:
  `src/features/file_storage/adapters/outbound/s3/` — all three files:
  `__init__.py`, `adapter.py`, and the 66-line AWS IAM/bucket
  `README.md`.
- **Code**:
  - `src/app_platform/config/settings.py` (narrow `storage_backend` to
    `Literal["local"]`; remove `storage_s3_bucket`/`storage_s3_region`
    fields + the S3 comment lines; reword the description comment)
  - `src/features/file_storage/composition/settings.py` (remove
    `s3_bucket`/`s3_region` fields/kwargs/assignments, narrow
    `StorageBackend` + the guard, remove the `validate()` `s3` arm,
    reword `validate_production` keeping the `APP_STORAGE_BACKEND`
    substring)
  - `src/features/file_storage/composition/container.py` (remove the
    `s3` arm, the deferred `boto3`-guarded import, and the module-level
    extra comment; defensive `else` becomes `# pragma: no cover`)
  - `src/features/file_storage/__init__.py`,
    `application/ports/file_storage_port.py`,
    `application/errors.py`, and (only if it names the removed backend)
    `adapters/outbound/local/adapter.py` — docstring/comment rewording
    only, no behaviour change. `tests/fakes/fake_file_storage.py`
    audited — no S3 naming, no change.
  - `.env.example` (remove two `APP_STORAGE_S3_*` keys + reword the
    storage comment)
  - `pyproject.toml` (remove the `s3` extra + comment block, the
    `uv sync --extra s3` install-modes line, and the `dev`-group
    `boto3~=1.34` / `moto~=5.0` / `boto3-stubs[s3]>=1.34` entries — see
    boto3 audit)
  - `uv.lock` (regenerate via `uv lock` after the `pyproject.toml`
    edits — boto3, botocore, moto, boto3-stubs and their now-unused
    transitives drop out)
  - **No edit to the composition call sites** (`src/main.py`,
    `src/worker.py`, `src/cli/create_super_admin.py`): audited — none
    pass any `s3_*` kwarg to `StorageSettings.from_app_settings`; the
    only `storage_s3_*` references are inside
    `StorageSettings.from_app_settings` itself and `AppSettings`.
    (Verify with a grep during implementation.)
- **boto3 audit conclusion**: `boto3`/`botocore`/`moto` appear in
  `pyproject.toml` in these roles. (1) The `s3 = ["boto3~=1.34"]` extra —
  **removed** (sole purpose is the deleted S3 adapter). (2) The `dev`
  group `boto3~=1.34`, `moto~=5.0`, `boto3-stubs[s3]>=1.34` — **removed**:
  a repo-wide search for `import boto3` / `boto3.` / `botocore` /
  `from moto` / `mock_aws` in `src/` returns exactly four files — the S3
  adapter, its unit test (`test_s3_adapter.py`), the contract test
  (de-parametrised here, losing its boto3/moto imports), and **nothing
  else**. After this change nothing in `src/` imports `boto3`/`botocore`/
  `moto`, so the dev deps go. (3) **No `boto3` Import Linter
  `forbidden_modules` entry exists** — verified: the only forbidden-
  modules architectural guardrails in `pyproject.toml` target FastAPI/
  SQLModel/SQLAlchemy/Alembic-style framework imports from
  domain/application, not `boto3`. There is **nothing to keep or remove**
  on that axis (this differs from step 4, where an `httpx`
  forbidden-modules guardrail had to be deliberately preserved).
  (4) The Renovate `boto3` + `botocore` co-versioned group
  (`renovate.json` and the `quality-automation` "Co-versioned package
  groups are declared" scenario) — **kept, untouched**: inert with
  boto3 absent, and re-touching it pre-empts the AWS-S3-adapter naming
  decision (same posture step 5 took with `arq + redis`). Explicitly
  flagged as a deliberate omission.
- **Tests**:
  - Delete `src/features/file_storage/tests/unit/test_s3_adapter.py`.
  - De-parametrise
    `src/features/file_storage/tests/contracts/test_file_storage_port_contract.py`
    (drop `s3` factory/id/fixture/constants + boto3/moto/S3 imports;
    keep `fake` + `local`; reword the module docstring).
  - Edit `src/features/file_storage/tests/unit/test_settings.py`
    (delete `test_s3_backend_requires_bucket`; drop the removed
    `s3_bucket=`/`s3_region=` kwargs from the two surviving tests).
  - **No edit to `src/app_platform/tests/test_settings.py`** — storage
    is disabled in `_VALID_PROD_ENV` (audited), so there is no
    always-present-refusal ripple; `_assert_only_always_present_refusals`
    stays at two entries; `test_production_rejects_local_storage_enabled`
    is unchanged and still resolves via the retained
    `APP_STORAGE_BACKEND` substring in the reworded message.
- **Migrations**: none. The S3 adapter was a runtime AWS-HTTP dispatch
  path with zero database footprint — no table, column, index, or
  persisted state is touched. `AppSettings.model_config` uses
  `extra="ignore"`, so any stale `APP_STORAGE_S3_BUCKET` /
  `APP_STORAGE_S3_REGION` env var in a deployed environment is silently
  ignored — no compatibility shim is required.
- **Docs** (S3 lines only — no wholesale rewrite; steps 9/10/11 own
  README/CLAUDE/operations re-framing): `docs/file-storage.md`,
  `docs/operations.md`, `docs/architecture.md`, `docs/observability.md`,
  `docs/development.md`, `README.md`, `CLAUDE.md`. `CONTRIBUTING.md`
  audited line-by-line and **has no S3-adapter reference** — no edit.
  `docs/background-jobs.md` audited — **no S3 reference** — no edit
  (despite the brief listing it as in scope).
- **Production behavior**: the production validator already refused
  `local` (when storage enabled) and accepted only `s3`. It now refuses
  `local` and accepts **no** file-storage backend — production-with-
  file-storage is not bootable until the real `aws_s3` adapter ships.
  Any deployment running `APP_STORAGE_BACKEND=s3` now fails fast at
  startup (the `from_app_settings` guard rejects the unknown backend) —
  intended; the current S3 backend is gone. Projects with
  `APP_STORAGE_ENABLED=false` are unaffected. This is the honest
  mid-cleanup state of an AWS-first starter, not a silent regression;
  see "Key decision" for the rejected alternative and why it is unsafe.
- **Quality gate**: `make quality` and `make test` MUST stay green after
  the removal. The file-storage contract suite MUST still pass for
  `fake` and `local`. Removing the adapter, its test, its contract
  parametrisation, its dependency extra, the dev boto3/moto deps, and
  its config surface together keeps the suite and the Import Linter
  contracts consistent. The Import Linter "File-storage does not import
  from other features" and outbound-isolation contracts are unaffected
  (the deleted package imported only `boto3`/`botocore` + in-repo
  file-storage modules).

## Out of scope (do NOT touch)

- The `local` adapter
  (`src/features/file_storage/adapters/outbound/local/`) — it is the
  dev/test default and the only surviving file-storage adapter.
- `FileStoragePort` and `FakeFileStorage` — unchanged (only S3-naming
  docstring asides on the port are reworded; the four-method contract
  is unchanged).
- The future real AWS S3 adapter (`aws_s3`) and any AWS/`boto3`/`moto`
  code or config — a later roadmap step. Do not add an `aws_s3` backend
  value, an `s3` accept-path to the validator, or any AWS code/config
  here.
- The `docs/operations.md` "production refuses to start if…" narrative
  reconciliation — ROADMAP step 11. Only delete S3 lines and state the
  minimal accurate post-removal reality.
- Any broader rewrite of `README.md` or `CLAUDE.md` beyond deleting S3
  lines / restating the file-storage row honestly — ROADMAP steps 9/10.
- The Renovate `boto3` + `botocore` co-versioned package group
  (`renovate.json` + the `quality-automation` "Co-versioned package
  groups are declared" scenario) — kept inert; re-touching it pre-empts
  the AWS-S3-adapter naming decision.
- The "Extending The Feature → Add a different cloud" guidance in
  `docs/file-storage.md` — it teaches the generic
  port-implementation/contract-test pattern, not the deleted adapter;
  only the clause asserting the S3 adapter ships is removed.

This change is strictly ROADMAP ETAPA I step 7. It does not advance
steps 8–12 (api.md, README/CLAUDE/operations rewrites, cli docs) or any
ETAPA II+ work, and it adds no AWS code.
