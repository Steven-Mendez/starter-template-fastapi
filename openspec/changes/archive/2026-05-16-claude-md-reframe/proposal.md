## Why

ROADMAP ETAPA I step 10 (`ROADMAP.md:54`): *"Actualizar `CLAUDE.md` con el
mismo encuadre: matriz de features post-limpieza, sección 'Adding a new
feature' (sin `_template`), reglas de producción actualizadas."* This is the
`CLAUDE.md` analogue of step 9's `readme-aws-first` (archived
`2026-05-16-readme-aws-first`): leave the repo honest after ETAPA I steps
1–9 (`_template` scaffold removed, SMTP/Resend/arq/SpiceDB removed,
`docs/api.md` de-Kanban'd, the S3 "stub" wording corrected in code and the
canonical `project-layout` spec, `README.md` reframed AWS-first).

`CLAUDE.md` is **already partially correct**: steps 1–7 made incremental
edits as they landed. The feature-matrix rows for `email`, `background_jobs`,
and `authorization`, the `## Production checklist`, the "Key env vars"
tables, and the "Adding a new feature" steps are already post-cleanup
accurate. A line-by-line audit of `CLAUDE.md` against the current source tree
(`ls src/features/` = seven features; the four infrastructure
`composition/settings.py` validators; the adapters present) found exactly
**two** false statements, both already flagged by the brief and by prior
steps' propagation notes — and **no third undocumented defect**:

1. **A false feature count.** `CLAUDE.md:50` reads "Six features ship out of
   the box." The matrix immediately below it (`CLAUDE.md:53–61`) correctly
   lists **seven** rows — `authentication`, `users`, `authorization`,
   `email`, `background_jobs`, `file_storage`, **and `outbox`**. The source
   tree ships seven feature packages under `src/features/`
   (`authentication/ users/ authorization/ email/ background_jobs/
   file_storage/ outbox/`). The "Six" wording is internally contradicted by
   its own table and by the code. This is the `CLAUDE.md` instance of the
   same undercount step 9 corrected in `README.md` (the README listed six
   features and was missing the `outbox` row entirely; here the row is
   present but the prose count is stale).

2. **A false adapter claim.** `CLAUDE.md:164` reads
   `` - `adapters/outbound/s3/` — stub; raises `NotImplementedError` ``.
   This is the same false "stub" wording ROADMAP step 7 (`fix-s3-stub-drift`)
   corrected in `src/features/file_storage/__init__.py` and folded into the
   canonical `project-layout` → "Documentation reflects the new layout"
   requirement, which now states (canonical `spec.md:99`) that no doc SHALL
   describe `S3FileStorageAdapter` as a "stub", as raising
   `NotImplementedError`, or as a placeholder. `S3FileStorageAdapter` is a
   real, contract-tested `boto3`-backed `FileStoragePort` implementation
   selected with `APP_STORAGE_BACKEND=s3` (`StorageBackend =
   Literal["local", "s3"]`; the file-storage `validate_production`
   refuses `local` when `APP_STORAGE_ENABLED=true` and requires
   `APP_STORAGE_S3_BUCKET` for `s3`). `CLAUDE.md:164` directly contradicts
   `CLAUDE.md:60`, which already says the feature ships "local + S3
   (`boto3`) adapters". Step 7's proposal explicitly **deferred** the
   `CLAUDE.md:164` propagation to this step; this change discharges that
   deferral. After it lands there is no outstanding S3-"stub" wording site.

The scaffold-recovery / removed-adapter audit the ROADMAP step implies was
**already satisfied by steps 1 and 3–6** and is **verified, not refabricated**
here. A grep of `CLAUDE.md` for `_template`, `feature-template`, `recover
the scaffold`, `recoverable`, `pre-removal`, `smtp`/SMTP, `resend`/Resend,
`spicedb`/SpiceDB, and `mailpit` returns **zero** hits. The two `arq`
references (`CLAUDE.md:157`, `:222`) already correctly describe `arq` as
**removed in ROADMAP ETAPA I step 5** and the worker as a runtime-agnostic
scaffold — they are accurate and are left untouched. The "Adding a new
feature" section (`CLAUDE.md:196–207`) already describes building the
`domain → application → adapters → composition` layout **from scratch**
("Create `src/features/<name>/` from scratch following the layer stack")
with no copy-the-scaffold or git-recovery prose — already step-1-correct.
The `## Production checklist` (`CLAUDE.md:230–247`) and the two "Key env
vars" tables (`CLAUDE.md:249–278`) match the current validators verbatim in
intent: email refuses `console` in production (AWS SES later), jobs refuses
`in_process` in production (AWS SQS + Lambda later), file-storage refuses
`local` in production when `APP_STORAGE_ENABLED=true`, and `outbox` must be
enabled in production — each one confirmed against the corresponding
`src/features/<feature>/composition/settings.py:validate_production`. None of
that correct prose is rewritten.

This change therefore makes **two surgical edits** and verifies the rest.
It is deliberately minimal: it does not rewrite correct content, does not
re-derive the module map, and does not pre-empt later ROADMAP steps.

### Scope boundary (other ROADMAP steps own the other files)

Only `CLAUDE.md` is edited here (plus the OpenSpec change artifacts).
`README.md` was completed by step 9 (`readme-aws-first`, archived) and is
**not** touched. `docs/operations.md` (step 11 — trimming the "production
refuses to start if…" master list to the post-cleanup reality) is **not**
touched; `CLAUDE.md` only carries a summary checklist, which this change
leaves consistent with the validators but does not expand into step 11's
operations.md rewrite. No other `docs/*.md` file is touched. A `src/cli/`
documentation section is **ROADMAP step 12** and is explicitly **not** added
to `CLAUDE.md` here — pre-empting step 12 is out of scope. The separate
`authorization`-spec Kanban defect is out of ETAPA I scope and is not
touched.

### No code, test, or migration changes

This is a documentation-accuracy change. No source, settings, env var,
dependency, middleware, migration, or test is added, removed, or renamed.
Every claim the corrected `CLAUDE.md` makes — the seven-feature inventory,
the adapters present (`console`, `in_process`, `local`, real `boto3` `s3`),
the production-validator behavior, the env-var defaults — is verifiable
against the current code and the ROADMAP. The pre-existing
`KANBAN_SKIP_TESTCONTAINERS` env-var name (a real testcontainers skip flag
in the codebase, unrelated to any Kanban feature) is left **exactly as-is** —
renaming it is a code change and is out of scope for this documentation step.

## What Changes

- **Feature count (`CLAUDE.md:50`).** Replace "Six features ship out of the
  box." with "Seven features ship out of the box." (matching the
  seven-row matrix at `CLAUDE.md:53–61` and the seven feature packages under
  `src/features/`). No other word of the surrounding sentence
  ("New features are created from scratch following the layer stack and
  per-feature conventions documented below.") changes — it is accurate.

- **S3 adapter line (`CLAUDE.md:164`).** Replace
  `` - `adapters/outbound/s3/` — stub; raises `NotImplementedError` `` with
  a code-true description of the real `boto3`-backed adapter selected via
  `APP_STORAGE_BACKEND=s3` (consistent with `CLAUDE.md:60`, the canonical
  `project-layout` S3 paragraph at `spec.md:99`, and
  `src/features/file_storage/__init__.py`). The words "stub",
  `NotImplementedError`, and "placeholder" MUST NOT appear for the S3
  adapter. This discharges ROADMAP step 7's deferred `CLAUDE.md`
  propagation.

- **Verify, do not churn.** The following are confirmed already correct by
  audit and are **left unchanged** (no edit):
  - The `email`, `background_jobs`, `authorization`, `file_storage`, and
    `outbox` matrix rows (`CLAUDE.md:55–61`) — already
    console-only/SES-later, in_process-only/SQS-later/runtime-agnostic
    scaffold, SpiceDB-free, "local + S3 (`boto3`) adapters", and the
    `outbox` row present.
  - The "Adding a new feature" section (`CLAUDE.md:196–207`) — already
    describes from-scratch creation; zero `_template` / scaffold-recovery /
    git-history-recovery residue.
  - The `## Production checklist` (`CLAUDE.md:230–247`) and both "Key env
    vars" tables (`CLAUDE.md:249–278`) — already match the four
    infrastructure `validate_production` validators (email/jobs/file-storage
    /outbox refusals) and the auth validator surface.
  - The two `arq` references (`CLAUDE.md:157`, `:222`) — already accurately
    describe `arq` as removed in ROADMAP ETAPA I step 5 and the worker as a
    runtime-agnostic scaffold.

- **Audit.** After editing, grep `CLAUDE.md` for `SMTP`/`smtp`,
  `Resend`/`resend`, `arq`, `SpiceDB`/`spicedb`, `mailpit`, `_template`,
  `feature-template`, `recover the scaffold`, `recoverable`, `pre-removal`,
  and `s3 stub` / `NotImplementedError`. The only acceptable remaining
  `arq` hits are the two "removed in ROADMAP ETAPA I step 5" references; the
  only acceptable `template`/`scaffold` hits are the
  `EmailTemplateRegistry` / `register_template` / `email_templates/` API
  references and the runtime-agnostic "worker scaffold" wording; the only
  acceptable `NotImplementedError` hit is the migration-`downgrade()` /
  destructive-migration convention prose (unrelated to S3). There must be
  zero removed-adapter, scaffold-recovery, or S3-stub references.

**Capabilities — Modified**

- `project-layout`: the existing "Documentation reflects the new layout"
  requirement is re-stated **verbatim** (all four SHALL paragraphs and all
  six existing scenarios carried forward unchanged, byte-matching the
  canonical header) and gains **one** scenario asserting that `CLAUDE.md`
  presents a code-true seven-feature inventory with no S3-"stub" or
  removed-adapter (SMTP/Resend/arq/SpiceDB) claim and no scaffold-recovery
  prose. This is the same requirement the directly-analogous prior
  doc-cleanup changes (`remove-template-scaffold-docs`, `fix-api-docs-kanban`,
  step 7's `fix-s3-stub-drift`, and step 9's `readme-aws-first`) refined; it
  already governs the content of `CLAUDE.md`.

**Capabilities — New**

- None.

<!-- SPEC-DELTA DECISION (for the orchestrator):

     There is no CLAUDE.md-specific requirement. The applicable existing
     requirement is `project-layout` → "Documentation reflects the new
     layout" (openspec/specs/project-layout/spec.md:93), which already
     governs the content of `CLAUDE.md`, `README.md`, and `docs/*.md`. As of
     this drafting the canonical block carries FOUR SHALL paragraphs
     (post-refactor-names; scaffold-recovery; the S3-adapter paragraph
     folded in by step 7 at canonical spec.md:99; the docs/api.md paragraph)
     and SIX scenarios (CLAUDE.md-new-names; README/docs src.-prefix;
     no-scaffold-recovery; api.md-routes-only; no-S3-stub [step 7]; README
     AWS-first inventory [step 9]). Asserting that `CLAUDE.md` carries a
     code-true seven-feature inventory with no S3-stub / removed-adapter /
     scaffold-recovery claim is a genuine refinement of that requirement, so
     this change ships a `## MODIFIED Requirements` delta that re-states it
     VERBATIM (all four paragraphs + all six existing scenarios carried
     forward unchanged, byte-matching the canonical header "Documentation
     reflects the new layout") plus ONE ADDED scenario. The strict validator
     requires every change to carry >=1 delta op; a zero-delta
     `--skip-specs` archive would fail `openspec validate --strict`, exactly
     as called out in the `remove-template-scaffold-docs`,
     `fix-api-docs-kanban`, and `readme-aws-first` SPEC-DELTA notes. Archive
     WITHOUT `--skip-specs` (`openspec archive claude-md-reframe`) so the new
     scenario folds into the canonical project-layout spec.

     IMPORTANT for the implementer/archiver: the verbatim restatement in
     specs/project-layout/spec.md MUST be reconciled against the CANONICAL
     openspec/specs/project-layout/spec.md "Documentation reflects the new
     layout" block AT ARCHIVE TIME. Step 7 (`fix-s3-stub-drift`) is still
     in flight on this same requirement (its change dir
     openspec/changes/fix-s3-stub-drift/ exists per the working tree). The
     restatement in this change's specs/project-layout/spec.md mirrors the
     CURRENT canonical block (4 paragraphs + 6 scenarios). If the canonical
     block changes again before this archives (a further refinement by step
     7's archive, or any other in-flight project-layout change), re-copy the
     then-current canonical text before archiving this change so the
     restatement still byte-matches and no prior refinement (src.-prefix,
     scaffold-recovery, api.md, S3-stub, README AWS-first) is dropped. -->

## Impact

- **Docs**: `CLAUDE.md` only — two surgical edits: the feature count
  (`:50` "Six" → "Seven") and the S3 adapter line (`:164` "stub; raises
  `NotImplementedError`" → real `boto3` adapter selected via
  `APP_STORAGE_BACKEND=s3`). Every other section is verified accurate and
  left unchanged (no churn): the seven-row feature matrix, the "Adding a new
  feature" steps, the `## Production checklist`, both "Key env vars" tables,
  and the two accurate `arq`-removed references. No other doc is touched
  (`README.md` = step 9, done; `docs/operations.md` = step 11; the
  `src/cli/` section = step 12, all explicitly out of scope).
- **Code**: none. No source, settings, env var, dependency, middleware,
  migration, or test is changed. `KANBAN_SKIP_TESTCONTAINERS` (a real,
  pre-existing testcontainers skip-flag env-var name) is left unchanged.
- **Migrations**: none.
- **Settings / env / production validator**: none. No env var is added,
  removed, or re-documented as required. The corrected `CLAUDE.md`
  production-checklist and env-var prose was audited against the four
  infrastructure `composition/settings.py:validate_production` validators
  (`email` refuses `console`, `background_jobs` refuses `in_process`,
  `file_storage` refuses `local` when `APP_STORAGE_ENABLED=true`, `outbox`
  must be enabled in production) and the auth validator surface; it already
  matches and is not rewritten.
- **Tests**: none deleted or edited.
- **Spec delta**: one `## MODIFIED Requirements` delta on the
  `project-layout` capability (`specs/project-layout/spec.md`) — the
  "Documentation reflects the new layout" requirement re-stated verbatim
  (all four existing SHALL paragraphs and all six existing scenarios carried
  forward) with one ADDED scenario about `CLAUDE.md`'s code-true
  seven-feature inventory and absence of S3-stub / removed-adapter /
  scaffold-recovery claims. No requirement is removed; no behavior outside
  documentation content changes. Archive WITHOUT `--skip-specs`; reconcile
  the verbatim restatement against the canonical block at archive time (see
  SPEC-DELTA DECISION — step 7 is in flight on the same requirement).
- **ROADMAP step 7 propagation discharged here**: step 7
  (`fix-s3-stub-drift`) corrected the S3-"stub" wording in code and the
  canonical spec but deliberately deferred the `CLAUDE.md:164` propagation
  to this step. This change discharges that deferral; after it lands there
  is **no** outstanding S3-"stub" wording site anywhere in the repo
  (`README.md:53` was discharged by step 9).
- **Feature-count fix**: `CLAUDE.md:50` "Six" → "Seven" reconciles the
  prose with its own seven-row matrix and the seven `src/features/`
  packages. This is the `CLAUDE.md` instance of the undercount step 9
  corrected in `README.md`.
- **ROADMAP step 1 status (scaffold-recovery removal)**: verified
  **already satisfied by ROADMAP step 1** (`remove-template-scaffold-docs`,
  archived 2026-05-16): zero `_template` / `feature-template` /
  `recover the scaffold` / `recoverable` / `pre-removal` hits in
  `CLAUDE.md`; the "Adding a new feature" section already frames the first
  move as build from scratch. This change does not fabricate work for that
  criterion; it only verifies and guards it.
- **ROADMAP step 12 deferral (explicit)**: no `src/cli/` command-reference
  section is added to `CLAUDE.md` here. Documenting `src/cli/` (what
  commands exist, how they are invoked, when they are used) in
  `README.md` + `CLAUDE.md` is ROADMAP step 12 and is explicitly out of
  scope for this step.
- **Production behavior**: unchanged. Documentation only.
- **Backwards compatibility**: any contributor who trusted `CLAUDE.md:50`
  ("Six features") or `CLAUDE.md:164` (S3 "stub raising
  `NotImplementedError`") was misled about the shipped surface; the
  corrected `CLAUDE.md` describes the seven features and the real
  `boto3`-backed S3 adapter that the code already ships.

## Out of scope (do NOT touch)

- `README.md` — completed by ROADMAP step 9 (`readme-aws-first`, archived
  2026-05-16). Not touched here.
- `docs/operations.md` — ROADMAP step 11 (trimming the "production refuses
  to start if…" master env-var list to the post-cleanup reality). The
  `CLAUDE.md` summary checklist is left consistent with the validators but
  is NOT expanded into step 11's operations.md rewrite.
- A `src/cli/` documentation section — ROADMAP **step 12**. Do not add,
  describe, or stub a CLI-commands section in `CLAUDE.md` here.
- `docs/*.md`, `ROADMAP.md`, `pyproject.toml`, `docker-compose.yml`, or any
  non-`CLAUDE.md` file (except the OpenSpec change artifacts).
- Any code, settings, env var (including the pre-existing
  `KANBAN_SKIP_TESTCONTAINERS` name), dependency, middleware, migration, or
  test — this is a documentation-accuracy change only.
- The separate `authorization`-spec Kanban defect — out of ETAPA I scope.
- The two accurate `arq`-removed references (`CLAUDE.md:157`, `:222`) and
  any already-correct prose — verified, not rewritten.

This change is strictly ROADMAP ETAPA I step 10. It does not advance steps
11–12, adds no AWS code, claims no unshipped AWS adapter, and changes no
runtime behavior.
