## Why

ROADMAP ETAPA I step 9 ("dejar el repo honesto"): *"Actualizar `README.md`
con el nuevo tagline AWS-first. Quitar la matriz de features que promete
SMTP/Resend/arq/SpiceDB. Quitar la mención al scaffold recuperable."* The
ROADMAP norte (line 3) is now: *"AWS-first FastAPI starter. Local dev sin
infraestructura, deploy a AWS — Cognito, SES, SQS, S3, RDS, ElastiCache. Una
sola opción opinada > tres opciones a medias."*

A line-by-line audit of `README.md` against the current source tree (after
ETAPA I steps 1–8: `_template` scaffold removed, SMTP/Resend/arq/SpiceDB
removed, `docs/api.md` de-Kanban'd, the S3 "stub" wording corrected in code
and the canonical project-layout spec) found the README wrong or stale in
four independent ways, not one:

1. **Generic, non-AWS-first framing.** The intro (lines 3–7) sells a
   "production-shaped starter for FastAPI services" that "bundles the four
   pieces of infrastructure every real backend needs". This pre-dates the
   AWS-first decision recorded in `ROADMAP.md` ("Decisiones ya tomadas") and
   gives no reader the project's actual norte: local dev with zero
   infrastructure, production targeting AWS, one opinionated option over
   three half-built ones. Nothing in the intro signals AWS as the single
   supported production target.

2. **A false adapter claim in the Feature Inventory.** `README.md:53` reads
   `` | `file_storage` | `FileStoragePort` plus `local` adapter and `s3`
   stub. | ``. This is the same false "stub" wording ROADMAP step 7
   (`fix-s3-stub-drift`) corrected in `src/features/file_storage/__init__.py`
   and folded into the canonical `project-layout` →
   "Documentation reflects the new layout" requirement, which now states
   (spec.md:99) that no doc SHALL describe `S3FileStorageAdapter` as a
   "stub" / `NotImplementedError` / placeholder. `S3FileStorageAdapter` is a
   real, contract-tested `boto3`-backed `FileStoragePort` implementation
   selected with `APP_STORAGE_BACKEND=s3` — exactly what ROADMAP step 24
   builds on. Step 7's proposal explicitly **deferred** the `README.md:53`
   propagation to this step; this change discharges that deferral.

3. **The `outbox` feature is missing entirely.** The Feature Inventory
   (lines 46–53) and the Project Structure tree (lines 89–95) list only six
   features. The source tree ships **seven**: `authentication`, `users`,
   `authorization`, `email`, `background_jobs`, `file_storage`, **and
   `outbox`** (`src/features/outbox/`, the `outbox_messages` table, the
   `DispatchPending` relay — added by `2026-05-13-add-outbox-pattern`,
   archived). The "four pieces of infrastructure" framing in the intro is
   doubly stale: it pre-dates both `outbox` and the AWS-first reframe.

4. **A stale "What's New" section with a broken link.** Lines 15–22 narrate
   only the `starter-template-foundation` change and link
   `openspec/changes/starter-template-foundation/` — a path that no longer
   exists (the change was archived to
   `openspec/changes/archive/2026-05-13-starter-template-foundation/`). The
   section pre-dates the entire ETAPA I cleanup (SMTP/Resend/arq/SpiceDB
   removal, `_template` removal, `outbox`) and now misrepresents the current
   state by omission; the link is a 404.

The scaffold-recovery mention the ROADMAP step asks to remove was **already
removed by ROADMAP step 1** (`remove-template-scaffold-docs`, archived
2026-05-16): a grep of `README.md` for `_template`, `feature-template`,
`recover the scaffold`, `recoverable`, and `pre-removal` returns zero hits,
and the intro already says "build your first feature from scratch". This
change therefore **verifies** that criterion is satisfied and does not
fabricate work for it.

This step rewrites only the inaccurate/stale prose: the tagline gets the
AWS-first framing (accurate to the *current* state — Cognito/SES/SQS/RDS/
ElastiCache are the project's *direction*, named as later roadmap steps, not
claimed as shipped), the Feature Inventory and Project Structure tree become
seven-feature-accurate with no false S3 "stub" claim, and the "What's New"
section is trimmed to an honest, link-correct minimal statement. The
already-correct structural sections (Quick Start, Tech Stack, Running Tests,
Building For Production, Common Commands, Troubleshooting, etc.) are kept;
only what is false or stale or required by the AWS-first reframe is touched.

### Scope boundary (other ROADMAP steps own the other files)

Only `README.md` is rewritten here (plus the OpenSpec change artifacts).
`CLAUDE.md` (ROADMAP step 10 — feature-matrix re-framing,
`CLAUDE.md:164`'s parallel S3-stub line), `docs/operations.md` (step 11 —
the "production refuses to start if…" trim), and the `src/cli/`
documentation section (**step 12** — what commands exist, how they are
invoked) are explicitly **NOT** addressed here and remain open. This change
adds **no** `src/cli/` section to `README.md`; pre-empting step 12 is out of
scope. No `docs/*.md` file is touched. Reviewers should reject any edit in
this change that touches a file other than `README.md` (and the OpenSpec
change artifacts).

### No code, test, or migration changes

This is a documentation-accuracy change. No source, settings, env var,
migration, or test is added, removed, or renamed. Every claim the rewritten
README makes — the seven-feature inventory, the adapters present (`console`,
`in_process`, `local`, real `boto3` `s3`), the env-var defaults, the
AWS-direction framing — is verifiable against the current code and the
ROADMAP. The rewrite introduces **no** claim that an AWS adapter or endpoint
exists that is not yet implemented: Cognito/SES/SQS/RDS/ElastiCache are
framed strictly as the project's target/direction at later roadmap steps,
matching the existing `email`/`background_jobs` rows' "arrives at a later
roadmap step" phrasing. The pre-existing `KANBAN_SKIP_TESTCONTAINERS`
env-var name (a real testcontainers skip flag in the codebase, unrelated to
any Kanban feature) is left **exactly as-is** — renaming it is a code change
and is out of scope for this documentation step.

## What Changes

- **Tagline / intro (lines 1–13).** Replace the "production-shaped starter
  for FastAPI services … bundles the four pieces of infrastructure" framing
  with an AWS-first framing in English, accurate to the current state:
  - State that this is an **AWS-first FastAPI starter**: local development
    needs no infrastructure beyond a Postgres container; production targets
    AWS; the project deliberately ships one opinionated option rather than
    three half-built ones (paraphrasing `ROADMAP.md:3`, in English, not a
    verbatim Spanish copy).
  - Frame Cognito / SES / SQS / S3 / RDS / ElastiCache as the project's
    **production direction at later roadmap steps**, NOT as already-shipped
    adapters. Keep the existing, accurate "the production X arrives at a
    later roadmap step" phrasing pattern already used by the `email` and
    `background_jobs` rows. Do **not** claim an AWS adapter, endpoint, or
    config that is not in the code today.
  - Keep the already-correct, step-1-authored "clone, run, then build your
    first feature from scratch following the documented hexagonal layout"
    sentence (lines 9–13) substantively intact — it is accurate and is the
    satisfied state of this step's "remove the recoverable-scaffold mention"
    criterion. It may be lightly re-sequenced to read naturally after the
    new AWS-first lede, but its meaning (build from scratch, not recover a
    scaffold) MUST NOT change and no scaffold-recovery prose may be
    reintroduced.

- **"What's New" section (lines 15–22).** Trim to an honest, minimal,
  link-correct statement of the current state. Either (a) replace the stale
  single-change narrative with one short sentence pointing readers at the
  ROADMAP for project direction and `openspec/changes/archive/` for change
  history (no per-change changelog), or (b) remove the section. It MUST NOT
  retain the broken `openspec/changes/starter-template-foundation/` link or
  imply the repository's history stops at `starter-template-foundation`. Do
  not turn this into a changelog.

- **Feature Inventory matrix (lines 44–57).** Make it seven-feature
  accurate and free of every removed-adapter and false-stub claim:
  - Fix `README.md:53`: describe `file_storage` as `FileStoragePort` plus a
    `local` adapter (dev/test) **and a real `boto3`-backed `s3` adapter**
    selected with `APP_STORAGE_BACKEND=s3`. The word "stub" /
    `NotImplementedError` / "placeholder" MUST NOT appear for the S3
    adapter (this discharges ROADMAP step 7's deferred README propagation
    and satisfies the canonical `project-layout` S3 scenario).
  - Add an `outbox` row: `OutboxPort`, the `outbox_messages` table, the
    `SessionSQLModelOutboxAdapter`, and the `DispatchPending` relay that
    runs in the worker — phrased to match the canonical CLAUDE.md/
    architecture description.
  - Keep the already-accurate `email` row (`console` only; production email
    via AWS SES at a later roadmap step) and `background_jobs` row
    (`in_process` only; production AWS SQS + a Lambda worker at a later
    roadmap step; runtime-agnostic worker scaffold) — these are correct
    post-cleanup and need no change beyond consistency of phrasing. There
    are no SMTP / Resend / arq / SpiceDB rows to remove (the matrix never
    listed adapter-level rows for them, and steps 1/3–6 already purged the
    adapters); confirm by audit that no SMTP/Resend/arq/SpiceDB token
    survives anywhere in `README.md`.

- **Project Structure tree (lines 74–101).** Add the missing
  `outbox/` feature directory so the tree matches the seven-feature source
  tree, and align the `worker.py` comment with the
  runtime-agnostic-scaffold reality already documented elsewhere in the
  README (it builds, logs handlers/cron descriptors, exits non-zero). Do
  **not** undertake the broader `src/platform/` → `src/app_platform/`
  on-disk-label correction here — the `src.`-prefix prose rule is governed
  by step 1's already-satisfied `project-layout` scenario, and a full tree
  re-derivation is out of this step's brief; limit tree edits to the
  `outbox` omission and the `worker.py` comment so the tree stops
  contradicting the (correct) Feature Inventory.

- **"Starting A New Project" / intro consistency.** Verify (do not rewrite)
  that the build-from-scratch guidance authored by step 1 remains intact and
  no scaffold-recovery prose is reintroduced by the tagline edit. This
  criterion is **already satisfied by step 1**; this change only guards it.

- **Audit.** After editing, grep `README.md` for `SMTP`, `Resend`, `arq`,
  `SpiceDB`/`spicedb`, `mailpit`, `_template`, `feature-template`,
  `recover the scaffold`, `recoverable`, and `s3 stub` /
  `NotImplementedError`. The only acceptable remaining "template" hits are
  the project name `starter-template-fastapi` and unrelated prose; there
  must be zero removed-adapter, scaffold-recovery, or S3-stub references.

**Capabilities — Modified**
- `project-layout`: the existing "Documentation reflects the new layout"
  requirement is re-stated verbatim and gains **one** scenario asserting
  that `README.md` presents the AWS-first framing (AWS as the single
  production target / direction, with AWS services named as later roadmap
  steps, not as shipped adapters) and a feature inventory that matches the
  seven features in the source tree with no removed-adapter
  (SMTP/Resend/arq/SpiceDB) or S3-"stub" claim. This is the same
  requirement the directly-analogous prior doc-cleanup changes
  (`remove-template-scaffold-docs`, `fix-api-docs-kanban`, and step 7's
  `fix-s3-stub-drift`) refined; it already governs the content of
  `README.md`.

**Capabilities — New**
- None.

<!-- SPEC-DELTA DECISION (for the orchestrator):

     There is no README-specific requirement. The applicable existing
     requirement is `project-layout` → "Documentation reflects the new
     layout" (openspec/specs/project-layout/spec.md:93), which already
     governs the content of `CLAUDE.md`, `README.md`, and `docs/*.md` and
     was last refined by step 7's `fix-s3-stub-drift` (it now carries the
     S3-adapter paragraph at spec.md:99 and the "No documentation describes
     the real S3 adapter as a stub" scenario at spec.md:130). Asserting
     that `README.md` carries the AWS-first framing and a code-true
     seven-feature inventory is a genuine refinement of that requirement,
     so this change ships a `## MODIFIED Requirements` delta that re-states
     it VERBATIM (all five paragraphs + all five existing scenarios carried
     forward unchanged, byte-matching the canonical header
     "Documentation reflects the new layout") plus ONE ADDED scenario. The
     strict validator requires every change to carry >=1 delta op; a
     zero-delta `--skip-specs` archive would fail `openspec validate
     --strict`, exactly as called out in the `remove-template-scaffold-docs`
     and `fix-api-docs-kanban` SPEC-DELTA notes. Archive WITHOUT
     `--skip-specs` (`openspec archive readme-aws-first`) so the new
     scenario folds into the canonical project-layout spec.

     IMPORTANT for the implementer/archiver: the verbatim restatement in
     specs/project-layout/spec.md MUST be reconciled against the CANONICAL
     openspec/specs/project-layout/spec.md "Documentation reflects the new
     layout" block AT ARCHIVE TIME. Step 7 (`fix-s3-stub-drift`) is in
     flight on this same requirement; if step 7 archives first and further
     amends that block, re-copy the then-current canonical text before
     archiving this change so the restatement still byte-matches and no
     prior refinement (src.-prefix, scaffold-recovery, api.md, S3-stub) is
     dropped. -->

## Impact

- **Docs**: `README.md` only — the tagline/intro reframed AWS-first, the
  "What's New" section trimmed and de-linked, the Feature Inventory made
  seven-feature accurate with the false `s3 stub` claim corrected to "real
  `boto3` `s3` adapter", and the Project Structure tree's `outbox`
  omission + `worker.py` comment fixed. No other doc is touched
  (CLAUDE.md = step 10, `docs/operations.md` = step 11, the `src/cli/`
  section = step 12, all explicitly out of scope).
- **Code**: none. No source, settings, env var, dependency, middleware,
  migration, or test is changed. In particular `KANBAN_SKIP_TESTCONTAINERS`
  (a real, pre-existing testcontainers skip-flag env-var name, not a Kanban
  feature) is left unchanged — renaming it is a code change and out of
  scope; the README leaves the name as-is.
- **Migrations**: none.
- **Settings / env / production validator**: none. No env var is added,
  removed, or re-documented as required. No AWS adapter, endpoint, or
  config is claimed to exist; AWS services are framed strictly as the
  project's direction at later roadmap steps.
- **Tests**: none deleted or edited.
- **Spec delta**: one `## MODIFIED Requirements` delta on the
  `project-layout` capability (`specs/project-layout/spec.md`) — the
  "Documentation reflects the new layout" requirement re-stated verbatim
  (all existing paragraphs and scenarios carried forward) with one ADDED
  scenario about README's AWS-first framing and seven-feature inventory
  accuracy. No requirement is removed; no behavior outside documentation
  content changes. Archive WITHOUT `--skip-specs`; reconcile the verbatim
  restatement against the canonical block at archive time (see SPEC-DELTA
  DECISION — step 7 is in flight on the same requirement).
- **ROADMAP step 7 propagation discharged here**: step 7
  (`fix-s3-stub-drift`) corrected the S3-"stub" wording in code and the
  canonical spec but deliberately deferred `README.md:53` to this step.
  This change discharges that deferral; after it lands, `CLAUDE.md:164`
  (the parallel S3-stub line) remains the only outstanding S3-wording site,
  owned by ROADMAP step 10.
- **ROADMAP step 1 status (scaffold-recovery removal)**: the ROADMAP step-9
  line asks to "remove the recoverable-scaffold mention". Verified
  **already satisfied by ROADMAP step 1** (`remove-template-scaffold-docs`,
  archived 2026-05-16): zero `_template` / `feature-template` /
  `recover the scaffold` / `recoverable` / `pre-removal` hits in
  `README.md`, and the intro already frames the first move as build from
  scratch. This change does not fabricate work for that criterion; it only
  guards against reintroducing scaffold-recovery prose during the tagline
  edit.
- **Production behavior**: unchanged. Documentation only.
- **Backwards compatibility**: any reader who followed the broken
  `openspec/changes/starter-template-foundation/` link hit a 404, and the
  "four pieces of infrastructure" framing under-counted the shipped
  features; the rewritten README describes the seven features and the
  AWS-first direction that the code and ROADMAP already reflect.

## Out of scope (do NOT touch)

- `CLAUDE.md` — ROADMAP step 10 (feature-matrix re-framing,
  production-rule trim, the parallel `CLAUDE.md:164` S3-stub line). Leave
  every CLAUDE.md reference, including its S3-stub wording, untouched here.
- `docs/operations.md` — ROADMAP step 11 ("production refuses to start
  if…" trim).
- A `src/cli/` documentation section — ROADMAP **step 12**. Do not add,
  describe, or stub a CLI-commands section in `README.md` here.
- `docs/*.md`, `ROADMAP.md`, `pyproject.toml`, `docker-compose.yml`, or
  any non-`README.md` file (except the OpenSpec change artifacts).
- Any code, settings, env var (including the pre-existing
  `KANBAN_SKIP_TESTCONTAINERS` name), dependency, middleware, migration,
  or test — this is a documentation-accuracy change only.
- The broader `src/platform/` → `src/app_platform/` on-disk-label
  question and a full Project Structure tree re-derivation — the
  `src.`-prefix prose rule is governed by step 1's already-satisfied
  `project-layout` scenario; this change limits tree edits to the
  `outbox` omission and the `worker.py` comment.

This change is strictly ROADMAP ETAPA I step 9. It does not advance steps
10–12, adds no AWS code, claims no unshipped AWS adapter, and changes no
runtime behavior.
