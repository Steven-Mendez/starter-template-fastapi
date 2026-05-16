# Tasks — fix-s3-stub-drift

> Wording-only. No code, test, dependency, setting, `Literal`, or
> migration change. Do NOT modify the S3 adapter or its machinery.

## 1. Reword the false "stub" prose

- [x] 1.1 `src/features/file_storage/__init__.py` — in the module
  docstring, replace *"`s3` as a stub for production integration"*
  (line 4) with an accurate description: `s3` is a real `boto3`-backed
  adapter, selected with `APP_STORAGE_BACKEND=s3` (requires `boto3` /
  the `s3` extra and bucket configuration). Keep the accurate
  "ships … ready to be wired in" framing about the *feature* being
  unwired; remove only the false "stub" claim about the *adapter*.

- [x] 1.2 `docs/architecture.md` line 36 — feature-table row for
  `file_storage`: replace *"`FileStoragePort`, local adapter, S3 stub"*
  with a description of a real `boto3`-backed S3 adapter, matching the
  honest tone of the adjacent `email` / `background_jobs` rows.

- [x] 1.3 `docs/architecture.md` line 245 — Design-Decisions table row
  "S3 stub | The adapter raises `NotImplementedError` …": **rewrite
  both cells, keep the table row.** Replace with a code-true design
  decision, e.g. *"S3 adapter (provider-agnostic endpoint) | The
  `boto3` adapter takes no template-specific endpoint knob; operators
  point at R2 / MinIO / other S3-compatible services via
  `AWS_ENDPOINT_URL_S3` at the SDK level."* Do not delete the row.

- [x] 1.4 `docs/architecture.md` line 251 — Tradeoffs/Limitations
  bullet "The S3 file-storage adapter is a stub …": reframe as an
  operational prerequisite (the adapter is real `boto3`; running it in
  production requires `boto3` + bucket + IAM config — point at
  `docs/file-storage.md` and the S3 adapter `README.md`). Keep a bullet
  here so the IAM-setup expectation is not lost; do not delete it
  outright.

- [x] 1.5 `ROADMAP.md` line 48 — rewrite the step-7 line so it no
  longer asserts a non-existent `NotImplementedError` stub. State that
  the premise was false, that `S3FileStorageAdapter` is a real `boto3`
  adapter and is retained, and that step 7 corrected the stale "stub"
  wording across the docs. Set the checkbox to `[x]`. Touch only
  line 48 — do not renumber, restructure, or re-check any other ROADMAP
  line (line 121 is step 24's, leave it).

## 2. Audit-only (expected: no edit)

- [x] 2.1 Confirm `docs/file-storage.md` carries no false "stub" /
  `NotImplementedError` / "placeholder" S3 wording (it already
  describes the real `boto3` adapter; its line-5 "ships as scaffolding"
  refers to the unwired feature, which is accurate). Make no edit.

- [x] 2.2 Confirm `README.md` line 53 and `CLAUDE.md` line 164 are
  **left unchanged** (deferred to ROADMAP steps 9 / 10). Verify the
  proposal's propagation note is present so steps 9/10 land "real
  `boto3` adapter", not "stub".

## 3. Spec delta

- [x] 3.1 Verify the MODIFIED requirement name in
  `specs/project-layout/spec.md` byte-matches the canonical header
  `### Requirement: Documentation reflects the new layout`
  (`openspec/specs/project-layout/spec.md` line 93).

- [x] 3.2 Confirm the delta restates the full SHALL text, carries all
  existing scenarios forward unchanged (the `src.`-prefix, scaffold-
  recovery, and `docs/api.md` scenarios), narrows the S3 carve-out to
  the unwired-feature "ships as scaffolding" note, and adds the new
  "no doc calls the real S3 adapter a stub" scenario.

## 4. Validate

- [x] 4.1 `openspec validate fix-s3-stub-drift --strict` passes.
- [x] 4.2 Confirm no code/test/`pyproject.toml`/settings/`Literal`/
  migration file is in the diff — only the five wording sites in §1 and
  the OpenSpec change artifacts.
- [ ] 4.3 Archive WITHOUT `--skip-specs`
  (`openspec archive fix-s3-stub-drift`) so the new project-layout
  scenario folds into the canonical spec.
