## Why

ROADMAP ETAPA I step 7 is written as *"Eliminar stub S3 que levanta
`NotImplementedError`"* (`ROADMAP.md` line 48), and instructs that
`FileStoragePort` be left with only the `local` adapter "until step 23
adds the real one". **This premise is factually false.** A line-by-line
audit against the source tree found:

1. **There is no S3 stub to delete.**
   `src/features/file_storage/adapters/outbound/s3/adapter.py` is a
   fully-implemented, runnable `boto3` adapter:
   `S3FileStorageAdapter` builds a real `botocore`-configured client in
   `__post_init__` and implements `put` (`put_object`), `get`
   (`get_object`, with `NoSuchKey`/`404` mapped to
   `ObjectNotFoundError`), `delete` (`delete_object`), `list`
   (paginated `list_objects_v2`), and `signed_url` (`head_object`
   existence check + `generate_presigned_url`, with the 604800-second
   SigV4 ceiling enforced). **No port method raises
   `NotImplementedError`.** This is not the SpiceDB-stub pattern that
   ROADMAP step 6 removed; it is the opposite.

2. **The codebase already promises this is real.** The canonical
   capability spec `openspec/specs/file-storage/spec.md` contains a
   requirement literally named **"S3 adapter is a real boto3
   implementation"** ("The adapter SHALL NOT raise `NotImplementedError`
   from any port method … SHALL pass the same behavioural contract as
   the local adapter and the in-memory fake"), with scenarios pinned
   against a `moto`-backed client. `docs/file-storage.md` and
   `src/features/file_storage/adapters/outbound/s3/README.md` already
   describe the real adapter accurately.

3. **The real adapter is exactly what the ROADMAP wants kept.** ROADMAP
   step 24 (`aws_s3 adapter real`) targets a complete `boto3`
   implementation of `put`/`get`/`delete`/`signed_url` — which already
   exists. The "Decisiones ya tomadas" list of production-shaped non-AWS
   adapters to remove is explicit: *"SMTP, Resend, arq, SpiceDB"*. **S3
   is not on that list.** Deleting a working, contract-tested AWS-native
   adapter would be destructive and would contradict the AWS-first
   *norte*.

What is wrong here is **not the adapter — it is stale documentation
prose that lies about the adapter**, plus the false ROADMAP line itself.
Several in-tree docs still call the real adapter a "stub" / "raises
`NotImplementedError`" / "placeholder for production". Leaving those
false statements in place directly violates ETAPA I's stated goal,
*"dejar el repo honesto"* (leave the repo honest). Correcting them — and
correcting the false ROADMAP step-7 line — *is* the honest execution of
step 7.

### Decision (recorded 2026-05-16, by the repository owner)

The ROADMAP step-7 premise (an S3 stub raising `NotImplementedError`)
**was false**. Presented with the audit, the owner chose **Option A —
drift-fix, not deletion**:

- The real `boto3` `S3FileStorageAdapter` **is retained**, unchanged.
  It is precisely what ROADMAP step 24 calls for; deleting it would be
  destructive and would contradict the AWS-first *norte*. S3 is not on
  the "remove" list (SMTP, Resend, arq, SpiceDB) — it must not be
  treated as if it were.
- Step 7 is therefore re-interpreted as a **documentation-accuracy /
  drift fix**: correct only the prose that falsely calls the working
  adapter a stub, and correct the false ROADMAP line-48 text so the
  ROADMAP no longer asserts a non-existent stub.
- This decision is recorded here (not only in chat) so it is traceable
  in the repository: a future reader who finds ROADMAP step 24's "remove
  the step-7 stub" wording will find, in the archived change history,
  why there was never a stub to remove.

This change is **wording-only**. It deletes no code, no test, no
extra, no setting, no `Literal`, and no migration. An earlier internal
analysis had pre-planned step 7 as a deletion (collapse the
`StorageBackend` `Literal`, drop the `s3` extra, reword the validator).
That plan is **superseded by this decision** and is explicitly *not*
executed here.

## What Changes

Reword the small set of doc sites where prose falsely describes the
real `S3FileStorageAdapter` as a stub / `NotImplementedError` /
production placeholder, so the documentation matches the code. No
behaviour, code, test, dependency, setting, or migration changes.

- **`src/features/file_storage/__init__.py`** (module docstring, line 4):
  *"`s3` as a stub for production integration"* → state that `s3` is a
  real `boto3`-backed adapter selected with `APP_STORAGE_BACKEND=s3`
  (requiring `boto3` / the `s3` extra and bucket configuration), and
  that the feature itself ships unwired ("ready to be wired in") — the
  unwired-feature framing is accurate and is kept; only the
  false "stub" word is removed.

- **`docs/architecture.md` line 36** (feature-table row): *"`file_storage`
  | `FileStoragePort`, local adapter, S3 stub."* → describe a real
  `boto3` S3 adapter, matching the tone of the adjacent `email` /
  `background_jobs` rows that already say "production … arrives with AWS
  … at a later roadmap step" (here the AWS adapter already exists, so
  state that directly).

- **`docs/architecture.md` line 245** (the "S3 stub | The adapter raises
  `NotImplementedError` from its methods…" Design-Decisions table row):
  this row exists *solely* to explain a design decision about a stub
  that does not exist; every clause in it ("raises `NotImplementedError`
  from its methods", "A real implementation needs provider-specific
  choices") is false against the code. **Resolution: rewrite the row,
  do not delete it.** Deleting it would silently drop a Design-Decisions
  entry; the honest replacement is a real decision the code actually
  embodies — e.g. *"S3 adapter (provider-agnostic endpoint) | The
  `boto3` adapter takes no template-specific endpoint knob; operators
  point at R2 / MinIO / other S3-compatible services via
  `AWS_ENDPOINT_URL_S3` at the SDK level."* (This is a genuine,
  code-true design decision, already documented in
  `src/features/file_storage/adapters/outbound/s3/README.md` and the
  adapter docstring.) The implementer rewrites the row's left and right
  cells accordingly; the table itself stays.

- **`docs/architecture.md` line 251** (Tradeoffs/Limitations bullet):
  *"The S3 file-storage adapter is a stub. Filling it in requires
  `boto3` and IAM configuration outside the scope of a starter."* →
  this is no longer a limitation. Replace with the accurate operational
  note: the S3 adapter is a real `boto3` implementation; running it in
  production requires `boto3` (the `s3` extra) plus bucket + IAM
  configuration (see `docs/file-storage.md` /
  `src/features/file_storage/adapters/outbound/s3/README.md`). Keep it
  in the Tradeoffs section reframed as an operational prerequisite
  rather than deleting the bullet, so the IAM-setup expectation is not
  lost.

- **`ROADMAP.md` line 48** (the step-7 line itself): rewrite so it no
  longer asserts a non-existent stub. The replacement records the
  decision: the original premise was false (there was never an S3
  stub raising `NotImplementedError`); the `S3FileStorageAdapter` is a
  real `boto3` adapter and is **retained**; step 7 instead corrected the
  stale "stub" wording across the docs. Mark the item `[x]` (the
  honest, decided form of step 7 is complete once the prose is
  corrected). Only line 48 is rewritten — no other ROADMAP line is
  renumbered, restructured, or re-checked. (ROADMAP step 24's "Eliminar
  el 'stub eliminado' del paso 7" sub-bullet, line 121, is **not**
  edited here — it belongs to step 24's own future change; the
  Out-of-scope section notes how that future step should reconcile.)

**`docs/file-storage.md` — audited, no change.** Every S3 reference in
`docs/file-storage.md` already describes the real `boto3` adapter
correctly ("a real `boto3`-backed S3 adapter", `s3_client.put_object`,
etc.). Its line-5 phrase "ships as scaffolding ready to plug into your
own feature" describes the *feature being unwired by any consumer*, not
the adapter being a stub — it is accurate and is the exact carve-out the
`project-layout` "Documentation reflects the new layout" requirement
explicitly preserves. No edit is made to `docs/file-storage.md`.

**Capabilities — Modified**

- `project-layout`: the existing **"Documentation reflects the new
  layout"** requirement is restated verbatim, with two adjustments
  reconciling it with this change:
  1. Its current carve-out sentence preserves *"the file-storage S3
     'ships as scaffolding' **stub** note"* as out of scope. The word
     "stub" in that carve-out is itself the drift this change corrects;
     the restated requirement narrows the carve-out to the *unwired-
     feature* "ships as scaffolding" note (which is accurate and is
     kept) and explicitly stops blessing any "stub" /
     `NotImplementedError` description of the S3 adapter.
  2. A new scenario asserts that no `docs/*.md`, `CLAUDE.md`,
     `README.md`, or feature `__init__.py` describes
     `S3FileStorageAdapter` as a stub / `NotImplementedError` /
     production placeholder. The two existing scenarios and the
     `docs/api.md` clause/scenario are carried forward unchanged.
  This is a documentation-accuracy refinement of the same requirement
  the directly-analogous prior doc-cleanup change
  (`fix-api-docs-kanban`, archived 2026-05-16) refined; it already
  governs the content of `docs/*.md`. The strict validator requires
  every change to carry ≥1 delta op, and a docs-accuracy refinement of
  this requirement is the honest delta target.

**Capabilities — New**

- None.

<!-- SPEC-DELTA DECISION (for the orchestrator):

  Two capability specs mention the S3 adapter:

  * `file-storage` owns the requirement "S3 adapter is a real boto3
    implementation". That requirement is ALREADY CORRECT and asserts
    exactly the truth this change defends (real boto3, no
    NotImplementedError). This change does NOT touch the file-storage
    spec — there is no behavioural delta there, and re-stating a
    correct requirement with no change would be noise. The adapter,
    its tests, the `s3` extra, StorageSettings, the StorageBackend
    Literal, and the production validator are all UNCHANGED.

  * `project-layout` owns "Documentation reflects the new layout"
    (specs/project-layout/spec.md line 93). Its carve-out sentence
    (line 97) currently says the file-storage S3 "ships as scaffolding"
    *stub* note SHALL remain — and a docs-accuracy clause + scenario
    already live in this requirement from fix-api-docs-kanban. The
    honest delta for a docs-drift fix is therefore a single
    `## MODIFIED Requirements` delta on this requirement: restate it
    verbatim, narrow the S3 carve-out to the unwired-feature note (drop
    the word that blesses "stub"), and add one scenario that no doc
    calls the real S3 adapter a stub. The requirement name in the delta
    byte-matches the canonical header
    ("Documentation reflects the new layout"). Carry ALL existing
    scenarios forward unchanged (the archive step replaces the whole
    requirement block). Archive WITHOUT --skip-specs so the new
    scenario folds into the canonical project-layout spec. -->

## Impact

- **Docs / prose (wording-only)**: `src/features/file_storage/__init__.py`
  (docstring line 4), `docs/architecture.md` (line 36 feature-table
  row; line 245 Design-Decisions table row — *rewritten*, not deleted;
  line 251 Tradeoffs bullet — reframed as an operational prerequisite),
  and `ROADMAP.md` line 48 (rewritten + checkbox set to `[x]`). Nothing
  else is touched in any of these files.
- **`docs/file-storage.md`**: audited, **no change** — already accurate.
- **Code**: none. `S3FileStorageAdapter` and every other source module
  are unchanged. No `NotImplementedError` is added or removed (there was
  never one to remove).
- **Tests**: none. The `moto`-backed S3 contract suite and
  `test_s3_adapter.py` are unchanged and continue to pass; this change
  documents the behaviour they already enforce.
- **Dependencies / `pyproject.toml`**: none. The `s3` extra
  (`boto3`), the dev-group `boto3`/`moto`/`boto3-stubs`, the lockfile,
  and any Renovate grouping are untouched.
- **Settings / env / `Literal` / production validator**: none. The
  `StorageBackend` `Literal["local", "s3"]`, `StorageSettings`,
  `APP_STORAGE_*` env vars, and the production validator that refuses
  `APP_STORAGE_BACKEND=local` when `APP_STORAGE_ENABLED=true` are all
  unchanged. (Contrast: ROADMAP steps 3/4/5 collapsed a `Literal` and
  reworded a validator; step 7, under the recorded Option-A decision,
  does **not** — there is no non-AWS production backend to remove here,
  S3 *is* the AWS backend.)
- **Migrations**: none.
- **Spec delta**: one `## MODIFIED Requirements` delta on the
  `project-layout` capability ("Documentation reflects the new layout"),
  restated verbatim with the S3 carve-out narrowed and one ADDED
  scenario. The `file-storage` capability is **not** modified — its
  "S3 adapter is a real boto3 implementation" requirement is already
  correct and is the spec-level proof that the ROADMAP premise was
  false. Archive WITHOUT `--skip-specs`.
- **README / CLAUDE deferral (propagation note)**: `README.md` line 53
  (`file_storage` … `s3` stub) and `CLAUDE.md` line 164
  (`adapters/outbound/s3/` — stub; raises `NotImplementedError`) carry
  the same false wording but are **deliberately not edited here** —
  ROADMAP step 9 rewrites `README.md` wholesale and step 10 rewrites
  `CLAUDE.md` wholesale (post-cleanup feature matrix). Editing those
  lines now would collide with those steps. **Steps 9 and 10 MUST
  describe `file_storage`'s S3 adapter as a real `boto3` implementation
  (selected via `APP_STORAGE_BACKEND=s3`), never as a stub**, so the
  truth established here propagates into the rewritten files.
- **Production behaviour**: unchanged. Documentation only.
- **Backwards compatibility**: none affected. Any operator who set
  `APP_STORAGE_BACKEND=s3` was already getting a working `boto3`
  adapter; only the prose that wrongly told them it was a stub changes.

## Out of scope (do NOT touch)

- **The S3 adapter and its surrounding machinery.** Do not delete or
  modify `src/features/file_storage/adapters/outbound/s3/adapter.py`,
  its tests, the `s3` extra, the dev-group `boto3`/`moto` deps,
  `StorageSettings`, the `StorageBackend` `Literal`, the
  `build_file_storage_container` selection logic, or the production
  storage validator. This change is wording-only. (Recorded decision:
  Option A — drift-fix, not deletion.)
- **`README.md` line 53** — ROADMAP step 9 (AWS-first tagline + full
  feature-matrix rewrite). Leave the `s3 stub` wording for that step;
  it MUST land as "real `boto3` adapter" there.
- **`CLAUDE.md` line 164** — ROADMAP step 10 (post-cleanup feature
  matrix + production rules). Leave the
  "stub; raises `NotImplementedError`" wording for that step; it MUST
  land as "real `boto3` adapter" there.
- **`ROADMAP.md` line 121** (step 24's "Eliminar el 'stub eliminado'
  del paso 7" sub-bullet) and any other ROADMAP line. Only line 48 is
  rewritten. Step 24's own future change owns reconciling its
  now-incorrect sub-bullet (there was never a stub for step 7 to have
  "eliminated"); a one-line note is left for that step rather than
  editing step 24 here.
- **`docs/file-storage.md`** — already accurate; auditing it was in
  scope, editing it is not.
- **The `file-storage` capability spec.** Its "S3 adapter is a real
  boto3 implementation" requirement is correct; this change neither
  removes nor restates it.
- **The separate `authorization`-spec Kanban defect** flagged
  elsewhere — outside ETAPA I scope, not touched here.
- **Any AWS code / new S3 features** (KMS SSE, multipart upload,
  LocalStack integration tests) — those are ROADMAP step 24, not this
  step.

This change is strictly ROADMAP ETAPA I step 7, re-interpreted per the
2026-05-16 Option-A decision. It advances no other step, adds no code,
and changes no runtime behaviour.
