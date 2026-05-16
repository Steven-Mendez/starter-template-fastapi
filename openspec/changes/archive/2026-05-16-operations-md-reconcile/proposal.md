## Why

ROADMAP ETAPA I step 11 (`ROADMAP.md:56`): *"Actualizar `docs/operations.md`:
quitar de 'producción rechaza arrancar si…' todas las reglas relacionadas a
backends eliminados (`APP_EMAIL_BACKEND=console` ahora será la única no-AWS,
etc.). Recortar la lista a la realidad post-limpieza."* This is the
`docs/operations.md` analogue of step 9 (`readme-aws-first`, archived) and
step 10 (`claude-md-reframe`, archived): leave the operator-facing runbook
honest after ETAPA I steps 1–10 (SMTP/Resend/arq/SpiceDB removed, the S3
"stub" wording corrected, `README.md`/`CLAUDE.md` reframed AWS-first).

`docs/operations.md` is **939 lines and already substantially
post-cleanup-accurate**. ETAPA I steps 3–7 made incremental edits as they
landed. A line-by-line audit of the entire file against the current source
tree and the four infrastructure `composition/settings.py` production
validators (plus `AppSettings._validate_production_settings`) found that the
"production refuses to start if…" narrative is **already correct everywhere
the brief expected stale prose** — and surfaced **exactly one** genuine
stale env-var defect, plus **no second undocumented defect**:

1. **A phantom production env var in the Deployment Checklist
   (`docs/operations.md:173`).** The bullet reads *"Set `APP_WRITE_API_KEY`
   if write routes should require a shared key."* No such setting exists
   anywhere in `src/` — `rg 'WRITE_API_KEY|write_api_key' src/` returns
   **zero** hits. There is no `APP_WRITE_API_KEY` field on any
   `composition/settings.py` projection, no `sub_settings.py` projection,
   and no shared-key write-route auth mechanism in the inbound HTTP layer
   (every write route is gated by `require_authorization`, not an API key).
   This is the **same phantom** the canonical `project-layout` →
   "Documentation reflects the new layout" requirement already prohibits
   for `docs/api.md` (canonical `spec.md:125`: *"the document contains no
   reference to an `X-API-Key` header or an `APP_WRITE_API_KEY` setting (no
   such authentication mechanism exists in the code)"*). The same false
   setting survives in `docs/operations.md`'s Deployment Checklist, in the
   middle of the production-deployment instructions. Telling an operator to
   "set" a setting that the application never reads is a deployment-runbook
   defect: it implies a write-protection control that does not exist.

   The Environment Variable Reference (`docs/operations.md:708–842`) — which
   is the actual consolidated "the settings validator refuses to start when
   any of them are violated and `APP_ENVIRONMENT=production`" master list —
   correctly does **not** list `APP_WRITE_API_KEY` in any of its
   per-feature tables, because no settings class defines it. The defect is
   isolated to the prose Deployment Checklist bullet at `:173`; the
   consolidated reference table is already code-true and is **not** edited.

The removed-backend audit the ROADMAP step implies was **already satisfied
by ETAPA I steps 3–7** and is **verified, not refabricated** here. A grep of
`docs/operations.md` for `SMTP`/`smtp`, `Resend`/`resend`,
`SpiceDB`/`spicedb`, `mailpit`, `_template`, `feature-template`,
`recover the scaffold`, and `recoverable` returns **zero** hits. Every
surviving production-refusal statement and every backend env-var table row
was checked against the live validators and is already accurate (see
"Verify, do not churn" in **What Changes** for the itemised audit). None of
that correct prose is rewritten — *"recortar la lista a la realidad
post-limpieza"* here means **removing the one phantom that contradicts the
validators**, not rewording prose that already matches them.

This change therefore makes **one surgical edit** and verifies the rest. It
is deliberately minimal: it does not rewrite correct content, does not
re-derive the env-var reference, and does not pre-empt later ROADMAP steps.

### The production-refusal list already matches the validators (verified)

The real set of production-refusal rules the validators enforce today, each
confirmed against its source, and each already documented correctly in
`docs/operations.md`:

- **Email refuses `console` in production.** `APP_EMAIL_BACKEND=console` is
  the only accepted value; production has no email backend until AWS SES at
  a later roadmap step. Already correct at `docs/operations.md:806`
  (Email env table) — matches the email feature's
  `composition/settings.py:validate_production`.
- **Background jobs refuses `in_process` in production.**
  `APP_JOBS_BACKEND=in_process` is the only value; production has no job
  runtime until the AWS SQS adapter + a Lambda worker at a later roadmap
  step (the `arq` runtime was removed in ROADMAP ETAPA I step 5). Already
  correct at `docs/operations.md:589–604` (Background Jobs section + table)
  and `:813` (env table) — matches the background_jobs feature's
  `validate_production`.
- **File storage refuses `local` when `APP_STORAGE_ENABLED=true` in
  production.** The real `boto3`-backed `s3` adapter is the production
  backend (`StorageBackend = Literal["local", "s3"]`; `s3` is **not** a
  stub — ETAPA I step 7 corrected that wording). Already correct at
  `docs/operations.md:839` (env table; *"Must be `s3` in production when
  `APP_STORAGE_ENABLED=true`"*) — matches the file_storage feature's
  `validate_production`.
- **Outbox must be enabled in production.** `APP_OUTBOX_ENABLED=true` is
  mandatory because request-path consumers write to the outbox
  unconditionally and the relay must drain it. Already correct at
  `docs/operations.md:823` (env table) — matches the outbox feature's
  `validate_production`.
- **The non-backend refusals** (JWT secret / issuer / audience required;
  CORS no `*`; trusted hosts no wildcard; cookie secure `true`; cookie
  samesite not `none`; docs disabled; RBAC enabled; return-internal-tokens
  `false`; `APP_AUTH_REDIS_URL` set; `APP_TRUSTED_PROXY_IPS` non-empty and
  never `0.0.0.0/0`) are already documented accurately at
  `docs/operations.md:170` (trusted hosts), `:387–390` (Redis URL),
  `:404–411` (trusted proxies), and the Environment Variable Reference rows
  `:721–791` — all matching `AppSettings._validate_production_settings`
  and the per-feature `validate_production` methods.

None of those statements names a removed backend (SMTP/Resend/arq/SpiceDB)
as if selectable, and none is rewritten by this change. The S3 adapter is
described as the real production backend everywhere storage is discussed
(`:24`, `:35`, `:839–842`, `:881`), consistent with steps 7/9/10 — there is
**no** "stub" / `NotImplementedError` / "placeholder" wording for the S3
adapter anywhere in the file (the only `NotImplementedError` references in
`docs/operations.md`, at `:231/:236/:245/:259`, are the unrelated
destructive-migration `downgrade()` guard, which is out of scope and **not**
touched).

### Scope boundary (other ROADMAP steps own the other files)

Only `docs/operations.md` is edited here (plus the OpenSpec change
artifacts). `README.md` was completed by step 9 (`readme-aws-first`,
archived 2026-05-16) and `CLAUDE.md` by step 10 (`claude-md-reframe`,
archived 2026-05-16) — **neither is touched**. No other `docs/*.md` file is
touched. A `src/cli/` command-reference section is **ROADMAP step 12** and
is explicitly **not** added to `docs/operations.md` here (the file's
existing incidental `python -m cli.create_super_admin` /
`src/cli/create_super_admin.py` bootstrap-runbook mentions at `:302`/`:331`
are accurate operational prose, left exactly as-is — they are not a
command-reference section and documenting `src/cli/` as a catalogue is step
12's job). Pre-empting step 12 is out of scope.

### No code, test, or migration changes

This is a documentation-accuracy change. No source, settings, env var,
dependency, middleware, migration, or test is added, removed, or renamed.
Removing the `APP_WRITE_API_KEY` checklist bullet does **not** remove a
setting (no such setting exists); it removes a false instruction. Every
claim the corrected `docs/operations.md` makes — the backend env-var
defaults, the production-validator refusals, the worker-scaffold behaviour,
the real `boto3` S3 adapter — is verifiable against the current code and
the ROADMAP. The pre-existing `KANBAN_SKIP_TESTCONTAINERS` env-var name (a
real testcontainers skip flag, unrelated to any Kanban feature) does not
appear in `docs/operations.md` and is, in any case, left untouched —
renaming it would be a code change and is out of scope.

## What Changes

- **Deployment Checklist phantom env var (`docs/operations.md:173`).**
  Remove the bullet `- Set `APP_WRITE_API_KEY` if write routes should
  require a shared key.` `APP_WRITE_API_KEY` is read by no settings class
  and gates no route; write routes are authorized via
  `require_authorization`, not a shared key. This is the same phantom the
  canonical `project-layout` requirement already prohibits in `docs/api.md`
  (canonical `spec.md:125`). No replacement bullet is added — there is no
  real "shared key for write routes" knob to point at; the surrounding
  Deployment Checklist bullets (`:166–178`) are accurate and unchanged.

- **Verify, do not churn.** The following are confirmed already correct by
  the full-file audit and are **left unchanged** (no edit):
  - The Environment Variable Reference (`docs/operations.md:708–842`) —
    the consolidated "the settings validator refuses to start when any of
    them are violated" master list. Every per-feature table
    (`ApiSettings`, `DatabaseSettings`, `ObservabilitySettings`,
    `AuthenticationSettings`, `AuthorizationSettings`, `UsersSettings`,
    `EmailSettings`, `JobsSettings`, `OutboxSettings`, `StorageSettings`)
    matches the live `composition/settings.py` validators. It correctly
    does **not** list `APP_WRITE_API_KEY` (no settings class defines it).
  - The Email env-var row (`:806`) — `console`-only, production refuses
    it, SES later. Matches the email `validate_production`.
  - The Background Jobs section (`:583–604`) and env-var row (`:813`) —
    `in_process`-only, production refuses it, AWS SQS + Lambda later, arq
    removed in ROADMAP ETAPA I step 5. Matches the background_jobs
    `validate_production`.
  - The File Storage env-var rows (`:838–842`) and the S3 prose
    (`:24`, `:35`, `:881`) — real `boto3` `s3` backend, must be `s3` in
    production when `APP_STORAGE_ENABLED=true`. No "stub" /
    `NotImplementedError` / "placeholder" wording. Matches the
    file_storage `validate_production` and steps 7/9/10.
  - The Outbox env-var row (`:823`) — must be `true` in production.
    Matches the outbox `validate_production`.
  - The Redis-URL and trusted-proxy production refusals (`:387–390`,
    `:404–411`) and the trusted-hosts / docs / CORS / cookie / RBAC /
    return-internal-tokens production rules in the Authentication and API
    env tables — match `AppSettings._validate_production_settings`.
  - The worker-scaffold prose (`:78`, `:113–117`, `:124–126`,
    `:145–150`, `:594–617`) — accurately describes a runtime-agnostic
    scaffold that exits non-zero (no job runtime wired; arq removed in
    ROADMAP ETAPA I step 5; AWS SQS + Lambda later). No removed-backend
    claim.
  - The two `arq`-removed references (`:22`, `:116`) and the
    `:594` "removed in ROADMAP ETAPA I step 5" note — already accurate.
  - The destructive-migration `downgrade()` / `NotImplementedError` guard
    (`:219–273`) — unrelated to S3 or ETAPA I cleanup; legitimate and
    explicitly **not** touched.
  - The incidental `python -m cli.create_super_admin` /
    `src/cli/create_super_admin.py` bootstrap-runbook mentions
    (`:300–305`, `:331`) — accurate operational prose, **not** a
    `src/cli/` command-reference section; left as-is (step 12 owns the
    catalogue).

- **Audit.** After editing, grep `docs/operations.md` for `WRITE_API_KEY`,
  `X-API-Key`, `SMTP`/`smtp`, `Resend`/`resend`, `SpiceDB`/`spicedb`,
  `mailpit`, `_template`, `feature-template`, `recover the scaffold`, and
  `recoverable`. There must be **zero** `WRITE_API_KEY` / `X-API-Key` /
  removed-adapter hits. The only acceptable `arq` hits are the
  "removed in ROADMAP ETAPA I step 5" references; the only acceptable
  `scaffold` hits are the runtime-agnostic worker-scaffold wording; the
  only acceptable `NotImplementedError` hits are the destructive-migration
  `downgrade()` guard prose; the only acceptable `stub` hits are the
  unrelated "no row stub" GDPR retention note (`:924`); the only
  acceptable `recovery` hits are the DB restore-from-backup runbook.

**Capabilities — Modified**

- `project-layout`: the existing "Documentation reflects the new layout"
  requirement is re-stated **verbatim** (all four SHALL paragraphs and all
  seven existing scenarios carried forward unchanged, byte-matching the
  canonical header) and gains **one** scenario asserting that
  `docs/operations.md`'s production-deployment and production-refusal
  narrative matches the live settings validators and references no phantom
  `APP_WRITE_API_KEY` and no removed backend. This is the same requirement
  the directly-analogous prior doc-cleanup changes
  (`fix-api-docs-kanban`, step 7's `fix-s3-stub-drift`, step 9's
  `readme-aws-first`, step 10's `claude-md-reframe`) refined; it already
  governs the content of `docs/*.md`.

**Capabilities — New**

- None.

<!-- SPEC-DELTA DECISION (for the orchestrator):

     There is no operations.md-specific or production-validator-narrative
     requirement under openspec/specs/. The closest candidates were checked:
     `authentication` → "Every documented production refusal has a unit
     test" (openspec/specs/authentication/spec.md) governs the *unit-test
     coverage* of each refusal, not the operations.md prose; this change
     adds/removes no refusal and no test, so MODIFYing it would be a
     misfit. `project-layout` → "Documentation reflects the new layout"
     (openspec/specs/project-layout/spec.md:93) is the requirement that
     already governs the content of `CLAUDE.md`, `README.md`, and every
     `docs/*.md` file — including the explicit prohibition (canonical
     spec.md:125) of the phantom `APP_WRITE_API_KEY` setting that this
     change removes from `docs/operations.md`.

     As of this drafting the canonical "Documentation reflects the new
     layout" block carries FOUR SHALL paragraphs (post-refactor-names;
     scaffold-recovery; the S3-adapter paragraph folded in by step 7 at
     canonical spec.md:99; the docs/api.md paragraph at spec.md:101) and
     SEVEN scenarios (CLAUDE.md-new-names; README/docs src.-prefix;
     no-scaffold-recovery; api.md-routes-only; no-S3-stub [step 7]; README
     AWS-first inventory [step 9]; CLAUDE.md seven-feature inventory
     [step 10]). Asserting that `docs/operations.md`'s production narrative
     is validator-true and free of the `APP_WRITE_API_KEY` phantom is a
     genuine refinement of that requirement, so this change ships a
     `## MODIFIED Requirements` delta that re-states it VERBATIM (all four
     paragraphs + all seven existing scenarios carried forward unchanged,
     byte-matching the canonical header "Documentation reflects the new
     layout") plus ONE ADDED scenario. The strict validator requires every
     change to carry >=1 delta op; a zero-delta `--skip-specs` archive
     would fail `openspec validate --strict`, exactly as called out in the
     `fix-api-docs-kanban`, `readme-aws-first`, and `claude-md-reframe`
     SPEC-DELTA notes. Archive WITHOUT `--skip-specs`
     (`openspec archive operations-md-reconcile`) so the new scenario folds
     into the canonical project-layout spec.

     IMPORTANT for the implementer/archiver: the verbatim restatement in
     specs/project-layout/spec.md MUST be reconciled against the CANONICAL
     openspec/specs/project-layout/spec.md "Documentation reflects the new
     layout" block AT ARCHIVE TIME. Step 7 (`fix-s3-stub-drift`) may still
     be in flight on this same requirement (its change dir
     openspec/changes/fix-s3-stub-drift/ exists in the working tree). The
     restatement in this change's specs/project-layout/spec.md mirrors the
     CURRENT canonical block (4 paragraphs + 7 scenarios — note step 7's
     S3 paragraph at canonical spec.md:99 and S3 scenario at :130, plus
     step 9's README scenario at :137 and step 10's CLAUDE scenario at
     :147, are ALL already folded into the canonical file as read during
     drafting). If the canonical block changes again before this archives
     (a further refinement by step 7's archive, or any other in-flight
     project-layout change), re-copy the then-current canonical text before
     archiving this change so the restatement still byte-matches and no
     prior refinement (src.-prefix, scaffold-recovery, api.md, S3-stub,
     README AWS-first, CLAUDE seven-feature) is dropped. -->

## Impact

- **Docs**: `docs/operations.md` only — **one surgical edit**: remove the
  phantom `APP_WRITE_API_KEY` bullet from the Deployment Checklist
  (`:173`). Every other section is verified accurate and left unchanged
  (no churn): the Environment Variable Reference master list
  (`:708–842`), the Email / Background Jobs / File Storage / Outbox
  backend tables and prose, the Redis-URL / trusted-proxy / trusted-hosts
  / docs / CORS / cookie / RBAC / return-internal-tokens production rules,
  the worker-scaffold prose, the two accurate `arq`-removed references,
  the real-`boto3`-S3 prose, the destructive-migration `downgrade()`
  guard, and the incidental bootstrap-CLI runbook mentions. No other doc
  is touched (`README.md` = step 9, done; `CLAUDE.md` = step 10, done;
  the `src/cli/` command-reference section = step 12, explicitly out of
  scope).
- **Production-refusal list reconciliation (the core of step 11)**: the
  consolidated "production refuses to start if…" narrative was audited
  end-to-end against the four infrastructure
  `composition/settings.py:validate_production` validators (`email`
  refuses `console`; `background_jobs` refuses `in_process`;
  `file_storage` refuses `local` when `APP_STORAGE_ENABLED=true`; `outbox`
  must be enabled) and `AppSettings._validate_production_settings` (JWT
  secret/issuer/audience, CORS, trusted hosts, trusted proxies, cookie
  secure/samesite, docs, RBAC, return-internal-tokens, Redis URL). It
  **already matches the validators**; no surviving rule references a
  removed backend (SMTP/Resend/arq/SpiceDB) as selectable. The only
  validator-contradicting line in the whole file was the
  `APP_WRITE_API_KEY` phantom (a setting no validator and no settings
  class knows about), which this change removes — "recortar la lista a la
  realidad post-limpieza" discharged.
- **Code**: none. No source, settings, env var, dependency, middleware,
  migration, or test is changed. `APP_WRITE_API_KEY` is not a real
  setting, so removing the doc bullet removes no configuration surface.
- **Migrations**: none. The destructive-migration `downgrade()` /
  `NotImplementedError` guard prose (`:219–273`) is unrelated to ETAPA I
  cleanup and is **not** touched.
- **Settings / env / production validator**: none. No env var is added,
  removed, or re-documented as required. The corrected
  `docs/operations.md` production narrative was audited against the four
  infrastructure validators and `AppSettings._validate_production_settings`
  and already matches; it is not rewritten.
- **Tests**: none deleted or edited.
- **Spec delta**: one `## MODIFIED Requirements` delta on the
  `project-layout` capability (`specs/project-layout/spec.md`) — the
  "Documentation reflects the new layout" requirement re-stated verbatim
  (all four existing SHALL paragraphs and all seven existing scenarios
  carried forward) with one ADDED scenario about `docs/operations.md`'s
  validator-true production narrative and the absence of the
  `APP_WRITE_API_KEY` phantom. No requirement is removed; no behavior
  outside documentation content changes. Archive WITHOUT `--skip-specs`;
  reconcile the verbatim restatement against the canonical block at
  archive time (see SPEC-DELTA DECISION — step 7 may be in flight on the
  same requirement).
- **ROADMAP step 7 consistency**: the S3 adapter is described as the real
  `boto3`-backed production backend everywhere storage is discussed in
  `docs/operations.md` (`:24`, `:35`, `:839–842`, `:881`) — consistent
  with step 7's drift-fix, step 9's `README.md`, and step 10's
  `CLAUDE.md`. No "stub" / `NotImplementedError` / "placeholder" wording
  for the S3 adapter exists in the file; nothing here introduces or
  removes such wording.
- **ROADMAP step 12 deferral (explicit)**: no `src/cli/` command-reference
  section is added to `docs/operations.md` here. Documenting `src/cli/`
  (what commands exist, how they are invoked, when they are used) in
  `README.md` + `CLAUDE.md` is ROADMAP step 12 and is explicitly out of
  scope for this step. The existing accurate
  `python -m cli.create_super_admin` bootstrap-runbook mentions are left
  unchanged — they are operational prose, not a command catalogue.
- **Production behavior**: unchanged. Documentation only.
- **Backwards compatibility**: any operator who followed
  `docs/operations.md:173` and "set" `APP_WRITE_API_KEY` believed they had
  enabled a shared-key write-protection control. They did not — the
  application never reads that variable and every write route is
  authorized via `require_authorization`. The corrected checklist removes
  the false instruction so operators do not rely on a control that does
  not exist.

## Out of scope (do NOT touch)

- `README.md` — completed by ROADMAP step 9 (`readme-aws-first`, archived
  2026-05-16). Not touched here.
- `CLAUDE.md` — completed by ROADMAP step 10 (`claude-md-reframe`,
  archived 2026-05-16). Not touched here.
- A `src/cli/` documentation / command-reference section — ROADMAP
  **step 12**. Do not add, describe, or stub a CLI-commands catalogue in
  `docs/operations.md` here. The existing accurate
  `python -m cli.create_super_admin` bootstrap-runbook mentions
  (`:300–305`, `:331`) are operational prose and are left exactly as-is.
- The destructive-migration `downgrade()` / `NotImplementedError` guard
  section (`docs/operations.md:219–273`) — unrelated to ETAPA I cleanup
  and to S3; legitimate and left exactly as-is, including the unrelated
  "template-only schema that has never held production data" phrase
  (refers to DB schema lifetime, not the removed `_template` feature).
- `docs/*.md` (other than `docs/operations.md`), `ROADMAP.md`,
  `pyproject.toml`, `docker-compose.yml`, or any non-`docs/operations.md`
  file (except the OpenSpec change artifacts).
- Any code, settings, env var (including the pre-existing
  `KANBAN_SKIP_TESTCONTAINERS` name, which does not appear in
  `docs/operations.md`), dependency, middleware, migration, or test —
  this is a documentation-accuracy change only.
- Every already-correct production-refusal statement, backend env-var
  table row, worker-scaffold paragraph, and the two accurate
  `arq`-removed references — verified, not rewritten.
- The separate `authorization`-spec Kanban defect — out of ETAPA I scope.

This change is strictly ROADMAP ETAPA I step 11. It does not advance steps
12+, adds no AWS code, claims no unshipped AWS adapter, and changes no
runtime behavior.
