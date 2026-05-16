## Why

ROADMAP ETAPA I step 12 (`ROADMAP.md:58`): *"Documentar `src/cli/` en
`README.md` + `CLAUDE.md`: qué comandos existen, cómo se invocan, cuándo se
usan."* This is the **final ETAPA I step** — the last "leave the repo honest"
cleanup before ETAPA II.

`src/cli/` is a package of project-level composition roots (peers of
`src/main.py` and `src/worker.py`; features MUST NOT import it — enforced by
the `Features do not import the CLI composition root` Import Linter contract,
`pyproject.toml:657–672`). It ships **two** operator commands that the live
docs do not document as a catalogue:

1. **`src/cli/create_super_admin.py`** — create OR promote the first
   `system:main#admin`. It exists as a CLI rather than an HTTP endpoint to
   break the chicken-and-egg where creating the first admin would otherwise
   require an admin JWT to already exist. It is the explicit, on-demand
   alternative to the startup bootstrap path
   (`APP_AUTH_SEED_ON_STARTUP` + `APP_AUTH_BOOTSTRAP_SUPER_ADMIN_EMAIL/PASSWORD`)
   that `CLAUDE.md` already documents — same use case, run by hand instead of
   at startup.

2. **`src/cli/outbox_prune.py`** — one-shot prune of terminal outbox rows and
   stale dedup marks. It runs the **same `PruneOutbox` use case** the worker's
   hourly prune cron runs, so operator-driven and scheduled prunes cannot
   drift. It intentionally ignores `APP_OUTBOX_ENABLED` — an operator running
   the one-shot has already decided to prune.

Today neither `README.md` nor `CLAUDE.md` has a CLI / operational-commands
section. The closest live mentions are incidental: `make outbox-prune` appears
in the `Makefile` (`:27–28`) but not in either doc's command catalogue, and
`docs/operations.md` carries incidental bootstrap-runbook prose for
`create_super_admin` (explicitly left as operational prose by ETAPA I step 11,
which deferred the *catalogue* to this step). The prior ETAPA I doc steps
deferred this on purpose: the canonical `project-layout` →
"Documentation reflects the new layout" requirement currently asserts that
`README.md` "contains no `src/cli/` command-reference section (the latter is
owned by a later roadmap step)" (canonical `spec.md:145`) and that
`CLAUDE.md` "contains no `src/cli/` command-reference section (that is owned
by a later roadmap step)" (canonical `spec.md:155`). **This is that later
step.** It adds the deferred sections and refines the requirement so the
prohibition becomes a requirement to document the two commands accurately.

### Invocations verified against the code (not the docstrings)

Every command string, subcommand, flag, and env var below was read out of the
actual modules and the `Makefile`; **the code/Makefile convention wins over
the module docstrings** where they differ:

- **`create_super_admin`** — `argparse` (`create_super_admin.py:224–241`):
  a required subparser (`dest="command"`, `required=True`) with subcommand
  **`create-super-admin`** (`:230`). Flags: **`--email`** (required, `:236`)
  and **`--password-env`** (`:237`, `default="AUTH_BOOTSTRAP_PASSWORD"`). The
  password is read with `os.getenv(password_env)` (`:183`) — kept out of shell
  history / process listings; a missing/empty value raises
  `SystemExit("Environment variable <NAME> is required")` (`:184–185`).
  `BootstrapRefusedExistingUserError` and `BootstrapPasswordMismatchError`
  exit `2` (`:206`, `:214`); all `APP_*` config is read via `AppSettings()`
  (`:93`). There is **no** `make` target — it is invoked directly.
  **Docstring vs code discrepancy:** the module docstring invocation
  (`:15–19`) is `uv run python -m cli.create_super_admin create-super-admin
  --email … --password-env …` and omits `PYTHONPATH=src`. Every live
  `make` target (`Makefile:19/22/25/28`) and `CLAUDE.md`'s command block use
  `PYTHONPATH=src uv run python -m <module>`. **The Makefile convention wins:**
  the documented invocation MUST be
  `PYTHONPATH=src uv run python -m cli.create_super_admin create-super-admin --email <e> --password-env <ENVVAR>`.
- **`outbox_prune`** — `main(argv)` ignores `argv`
  (`outbox_prune.py:76`, `# noqa: ARG001`) and calls `run_once()`; there is
  **no subcommand and no flag**. Retention windows and batch size come from
  `OutboxSettings.from_app_settings(AppSettings())` (`:39–40`);
  `APP_OUTBOX_ENABLED` is **deliberately not consulted** (docstring `:17–21`).
  Exit `0` on success, `1` when the use case returns `Err` (`:64–65`, `:73`).
  It has a `make` target: **`make outbox-prune`**
  (`Makefile:27–28` = `PYTHONPATH=src uv run python -m cli.outbox_prune`).
  **Docstring vs code discrepancy:** the docstring invocation (`:14`) is
  `uv run python -m cli.outbox_prune` without `PYTHONPATH=src`; the live
  `make outbox-prune` recipe uses `PYTHONPATH=src`. **The Makefile convention
  wins.**

### Scope boundary

Only `README.md` and `CLAUDE.md` are edited (plus the OpenSpec artifacts).
This is **additive**: a tight, accurate CLI / operational-commands section in
each doc, matched to that doc's existing voice (README = prose + tables;
`CLAUDE.md` = terse command block). No `docs/*.md` is touched (step 11 already
closed `docs/operations.md` and explicitly deferred the catalogue here; its
incidental bootstrap-runbook prose stays as-is). No `src/cli/` code, no other
source, no test, no migration, no dependency, no env var, no `Makefile` change.
The module docstrings are **not** rewritten (the discrepancy is resolved in
the docs by following the Makefile convention, not by editing code).

### Consistency with ETAPA I steps 1–11 (no regression)

The new sections match the now-current AWS-first framing: seven features,
no `_template`/SMTP/Resend/arq/SpiceDB, the S3 adapter is a real `boto3`
adapter (not a "stub"), `console`/`in_process`/`local` are dev-only. The new
prose introduces none of those removed names and re-states no removed-backend
claim. The `create-super-admin` section cross-references — and does not
contradict — the existing `APP_AUTH_SEED_ON_STARTUP` /
`APP_AUTH_BOOTSTRAP_SUPER_ADMIN_EMAIL/PASSWORD` /
`APP_AUTH_BOOTSTRAP_PROMOTE_EXISTING` startup-bootstrap documentation in
`CLAUDE.md`. The pre-existing real `KANBAN_SKIP_TESTCONTAINERS` env-var name
is unrelated and untouched.

### No code, test, or migration changes

Documentation-accuracy change only. No source, settings, env var, dependency,
middleware, migration, `Makefile`, or test is added, removed, or renamed.
Every command string, subcommand, flag, exit code, and `APP_*` env var the new
sections state is verifiable against `src/cli/*.py` and the `Makefile` as
itemised above.

## What Changes

- **`README.md` — add a CLI / operational-commands section.** Insert a new
  `## Operational Commands` section documenting both CLI commands, placed
  immediately **after `## Common Commands`** (currently ending at
  `README.md:322`) and **before `## Troubleshooting`** (`:324`) — it belongs
  with the command-catalogue content and after the `make`-target table that
  cannot carry the "when to use / which env vars" semantics. For each command,
  in the README's prose-plus-table voice: **what it is**, the **exact
  invocation**, **when to use it**, and the **key `APP_*` / password env
  vars**:
  - **Create or promote the first system admin** —
    `PYTHONPATH=src uv run python -m cli.create_super_admin create-super-admin --email <email> --password-env <ENVVAR>`.
    `--email` required; `--password-env` defaults to `AUTH_BOOTSTRAP_PASSWORD`
    and names the env var holding the password (kept out of shell history /
    process listings); a missing value aborts. Reads `APP_*` config via
    `AppSettings`. Use it to bootstrap the very first `system:main#admin`
    when no admin (and thus no admin JWT) exists yet — the on-demand
    alternative to the `APP_AUTH_SEED_ON_STARTUP` /
    `APP_AUTH_BOOTSTRAP_SUPER_ADMIN_EMAIL/PASSWORD` startup path. Promoting an
    existing account requires `APP_AUTH_BOOTSTRAP_PROMOTE_EXISTING=true` plus
    the account's real password (default-deny: it exits non-zero otherwise).
  - **Prune the outbox once** — `make outbox-prune` (equivalently
    `PYTHONPATH=src uv run python -m cli.outbox_prune`). No flags. Deletes
    terminal (`delivered`/`failed`) outbox rows and stale dedup marks past
    their retention, in batches; same `PruneOutbox` code path as the worker's
    hourly prune cron. Retention/batch come from the `APP_OUTBOX_*` settings;
    `APP_OUTBOX_ENABLED` is **intentionally ignored** (the operator already
    decided to prune). Use it for an on-demand sweep without waiting for the
    worker cron.
- **`CLAUDE.md` — add the two commands to the `## Commands` block.** Inside
  the existing fenced `bash` block (`CLAUDE.md:7–45`), add a new
  `# Operational CLI` group **after the `# Migrations` group** (`:35–37`) and
  **before `# Run single test file`** (`:39`), in the file's terse
  one-line-comment command style, e.g.:
  - `PYTHONPATH=src uv run python -m cli.create_super_admin create-super-admin --email <e> --password-env <ENVVAR>`
    `# create/promote the first system:main#admin (on-demand alternative to APP_AUTH_SEED_ON_STARTUP bootstrap)`
  - `make outbox-prune`
    `# one-shot prune of terminal outbox rows + stale dedup marks (same code path as the worker prune cron; ignores APP_OUTBOX_ENABLED)`

  Do not duplicate the full module docstrings — summarise. Do not contradict
  the existing startup-bootstrap documentation in `CLAUDE.md`'s Authentication
  feature section and Key-env-vars tables; the CLI is presented as the
  explicit alternative to that startup path.
- **Verify, do not invent.** Before writing, the implementer MUST re-derive
  every command string, subcommand, flag, default, exit code, and `APP_*`
  env var from `src/cli/create_super_admin.py`, `src/cli/outbox_prune.py`,
  and the `Makefile` (`grep`/read the `argparse` definitions, the `__main__`
  invocation, the env-var reads, and the `make` recipes). No flag, env var,
  or subcommand may be documented that is not present in the code. Where a
  module docstring's invocation differs from the live `Makefile`/`CLAUDE.md`
  convention (no `PYTHONPATH=src`), the **code/Makefile convention wins** and
  is what gets documented.
- **No regression of ETAPA I steps 1–11.** The new sections name no removed
  adapter (`_template`, `smtp`, `resend`, `arq`, `spicedb`/SpiceDB), describe
  the S3 adapter (if mentioned at all) only as a real `boto3` adapter, and
  keep the seven-feature AWS-first framing intact.

**Capabilities — Modified**

- `project-layout`: the existing "Documentation reflects the new layout"
  requirement is re-stated **verbatim** (all four SHALL paragraphs and all
  eight existing scenarios carried forward unchanged, byte-matching the
  canonical header) and gains **one** ADDED scenario asserting that
  `README.md` and `CLAUDE.md` each carry an accurate, code-true CLI /
  operational-commands section documenting both `src/cli/` commands (exact
  invocation, when to use, key env vars), and that the previously-asserted
  "no `src/cli/` command-reference section" sub-clauses in the README
  AWS-first inventory scenario and the CLAUDE seven-feature inventory scenario
  no longer hold. This is the same requirement the prior ETAPA I doc-cleanup
  changes (`fix-api-docs-kanban`, step 7 `fix-s3-stub-drift`, step 9
  `readme-aws-first`, step 10 `claude-md-reframe`, step 11
  `operations-md-reconcile`) refined; it already governs the content of
  `README.md`, `CLAUDE.md`, and every `docs/*.md` file.

**Capabilities — New**

- None.

<!-- SPEC-DELTA DECISION (for the orchestrator):

     There is no CLI-specific or command-catalogue requirement under
     openspec/specs/. `project-layout` → "Documentation reflects the new
     layout" (canonical openspec/specs/project-layout/spec.md:93) is the
     requirement that already governs the content of CLAUDE.md, README.md,
     and every docs/*.md file. It does more than govern it: its README
     AWS-first inventory scenario (canonical spec.md:137–145) and its
     CLAUDE seven-feature inventory scenario (canonical spec.md:147–156)
     each contain an explicit sub-clause asserting the doc "contains no
     src/cli/ command-reference section ... owned by a later roadmap step"
     (spec.md:145 and spec.md:155). This step is that later step, so adding
     the sections is a genuine, in-scope refinement of exactly this
     requirement — not a misfit.

     As of this drafting the canonical "Documentation reflects the new
     layout" block carries FOUR SHALL paragraphs (post-refactor-names;
     scaffold-recovery; the S3-adapter paragraph folded in by step 7 at
     canonical spec.md:99; the docs/api.md paragraph at spec.md:101) and
     EIGHT scenarios:
       1. CLAUDE.md commands and module map use the new names
       2. README and docs prose drop the src. prefix
       3. Docs do not instruct recovering the removed scaffold
       4. API reference documents only routes that exist in code
       5. No documentation describes the real S3 adapter as a stub  [step 7]
       6. README presents the AWS-first framing and a code-true feature
          inventory  [step 9]
       7. CLAUDE.md presents a code-true seven-feature inventory with no
          stale-adapter claims  [step 10]
       8. operations.md production narrative matches the live settings
          validators  [step 11]
     (All eight are present in the canonical file as read during drafting:
     openspec/specs/project-layout/spec.md:103–165.)

     This change ships a `## MODIFIED Requirements` delta that re-states the
     requirement VERBATIM (all four paragraphs + all eight existing
     scenarios carried forward unchanged, byte-matching the canonical header
     "Documentation reflects the new layout") plus ONE ADDED scenario
     ("README.md and CLAUDE.md document the src/cli/ operational commands").
     The strict validator requires every change to carry >=1 delta op; a
     zero-delta `--skip-specs` archive would fail
     `openspec validate --strict`, exactly as called out in the
     fix-api-docs-kanban, readme-aws-first, claude-md-reframe, and
     operations-md-reconcile SPEC-DELTA notes. Archive WITHOUT
     `--skip-specs` (`openspec archive document-src-cli`) so the new
     scenario folds into the canonical project-layout spec.

     IMPORTANT for the implementer/archiver: the verbatim restatement in
     specs/project-layout/spec.md MUST be reconciled against the CANONICAL
     openspec/specs/project-layout/spec.md "Documentation reflects the new
     layout" block AT ARCHIVE TIME. Step 7 (fix-s3-stub-drift) and step 11
     (operations-md-reconcile) may still be in flight on this same
     requirement (their change dirs exist in the working tree). The
     restatement in this change's specs/project-layout/spec.md mirrors the
     CURRENT canonical block (4 paragraphs + 8 scenarios, including step
     11's operations.md scenario at canonical spec.md:158, which is already
     folded in as read during drafting). If the canonical block changes
     again before this archives, re-copy the then-current canonical text
     before archiving so the restatement still byte-matches and no prior
     refinement (src.-prefix, scaffold-recovery, api.md, S3-stub, README
     AWS-first, CLAUDE seven-feature, operations.md) is dropped.

     Note: scenario 6 (README AWS-first) ends with "...and no `src/cli/`
     command-reference section (the latter is owned by a later roadmap
     step)" and scenario 7 (CLAUDE seven-feature) contains "`CLAUDE.md`
     contains no `src/cli/` command-reference section (that is owned by a
     later roadmap step)". This change does NOT rewrite those scenarios in
     the verbatim restatement (they are carried byte-for-byte). The newly
     ADDED scenario instead asserts the now-true post-step-12 state (both
     docs DO carry the section). The narrowly-stale sub-clauses in
     scenarios 6 and 7 are a known, accepted consequence of the canonical
     spec being a verbatim-carry-forward ledger; the orchestrator may, at a
     later archive, choose to MODIFY scenarios 6/7 to drop the now-false
     sub-clause, but that is OUT OF SCOPE for step 12 (whose brief is
     additive doc edits to README.md + CLAUDE.md only) and is NOT done here.
     -->

## Impact

- **Docs**: `README.md` and `CLAUDE.md` **only**.
  - `README.md`: a new `## Operational Commands` section between
    `## Common Commands` (`:322`) and `## Troubleshooting` (`:324`)
    documenting both `src/cli/` commands (what / exact invocation / when /
    key env vars), in the README's prose+table voice.
  - `CLAUDE.md`: a new `# Operational CLI` group inside the existing
    `## Commands` bash fence, after `# Migrations` (`:37`) and before
    `# Run single test file` (`:39`), in the terse one-line-comment style.
  - No `docs/*.md` is touched (step 11 closed `docs/operations.md` and
    deferred the catalogue here; its incidental bootstrap-runbook prose
    stays as-is).
- **Two commands documented**:
  - `src/cli/create_super_admin.py` — invocation
    `PYTHONPATH=src uv run python -m cli.create_super_admin create-super-admin
    --email <email> --password-env <ENVVAR>`; `--email` required;
    `--password-env` default `AUTH_BOOTSTRAP_PASSWORD`; password read from the
    named env var; config via `APP_*`/`AppSettings`; on-demand alternative to
    the `APP_AUTH_SEED_ON_STARTUP` /
    `APP_AUTH_BOOTSTRAP_SUPER_ADMIN_EMAIL/PASSWORD` startup bootstrap;
    promoting an existing account needs
    `APP_AUTH_BOOTSTRAP_PROMOTE_EXISTING=true` + the real password.
  - `src/cli/outbox_prune.py` — invocation `make outbox-prune`
    (= `PYTHONPATH=src uv run python -m cli.outbox_prune`); no flags; prunes
    terminal outbox rows + stale dedup marks via the same `PruneOutbox` code
    path as the worker prune cron; retention/batch from `APP_OUTBOX_*`;
    `APP_OUTBOX_ENABLED` intentionally ignored.
- **Invocations verified against `src/cli/`**: confirmed. Every command
  string, subcommand, flag, default, exit code, and `APP_*` env var the new
  sections state was derived from `src/cli/create_super_admin.py`
  (`argparse` `:224–241`, password read `:183–185`, settings `:93`),
  `src/cli/outbox_prune.py` (`main`/`run_once` `:37–82`, no-flag note `:76`,
  `APP_OUTBOX_ENABLED`-ignored docstring `:17–21`), and the `Makefile`
  (`outbox-prune` `:27–28`). The two module-docstring invocations omit
  `PYTHONPATH=src`; the live `Makefile`/`CLAUDE.md` convention includes it —
  **the Makefile convention is what is documented** (code wins; docstrings
  not edited).
- **Code**: none. No `src/cli/` change, no other source, no settings, no env
  var, no dependency, no middleware, no `Makefile` change.
- **Migrations**: none.
- **Tests**: none deleted, added, or edited.
- **Settings / env / production validator**: none. No env var is added,
  removed, or re-documented as required; the documented `APP_*` names already
  exist.
- **Spec delta**: one `## MODIFIED Requirements` delta on the
  `project-layout` capability (`specs/project-layout/spec.md`) — the
  "Documentation reflects the new layout" requirement re-stated verbatim
  (all four existing SHALL paragraphs and all eight existing scenarios
  carried forward) with one ADDED scenario about the `README.md` /
  `CLAUDE.md` CLI / operational-commands sections. No requirement is removed;
  no behavior outside documentation content changes. Archive WITHOUT
  `--skip-specs`; reconcile the verbatim restatement against the canonical
  block at archive time (see SPEC-DELTA DECISION — steps 7 and 11 may be in
  flight on the same requirement).
- **ROADMAP**: this is the **last ETAPA I step**. At implement/archive time
  (by the implementer/orchestrator, **not** the spec-writer now):
  flip `ROADMAP.md:58` step 12 `- [ ]` → `- [x]`, **and** update the bottom
  progress-checklist table row `| I — Limpieza | 1–12 | Pendiente |` →
  `| I — Limpieza | 1–12 | Completado |` (ETAPA I fully closed). Both edits
  are part of implement/archive, not this proposal.
- **Production behavior**: unchanged. Documentation only.
- **Backwards compatibility**: purely additive. No existing command,
  invocation, env var, or `make` target changes; readers gain an accurate
  catalogue of two commands that already exist.

## Out of scope (do NOT touch)

- Any `docs/*.md` — `docs/operations.md` was closed by ETAPA I step 11
  (`operations-md-reconcile`) and explicitly deferred the `src/cli/`
  *catalogue* to this step; its incidental
  `python -m cli.create_super_admin` bootstrap-runbook prose is operational
  prose and is **not** edited here. No `docs/` file is touched.
- `src/cli/*.py` and their module docstrings — the docstring-vs-Makefile
  `PYTHONPATH=src` discrepancy is resolved **in the docs** by following the
  Makefile convention, not by editing code. No code change.
- The `Makefile` — `make outbox-prune` already exists; documenting it adds
  no target and edits no recipe. There is intentionally **no** `make`
  target for `create_super_admin`; do not add one (out of scope — this step
  is doc-only).
- `ROADMAP.md` — the spec-writer does **not** flip the step-12 checkbox or
  the ETAPA I progress-table row now; that is done by the
  implementer/orchestrator at implement/archive time.
- Any code, settings, env var (including the pre-existing real
  `KANBAN_SKIP_TESTCONTAINERS` name), dependency, middleware, migration, or
  test — documentation-accuracy change only.
- The verbatim-carried scenarios 6 (README AWS-first) and 7 (CLAUDE
  seven-feature) in the `project-layout` requirement — they are carried
  byte-for-byte and **not** rewritten here even though their
  "no `src/cli/` command-reference section" sub-clauses become narrowly
  stale; the newly ADDED scenario asserts the now-true post-step-12 state.
  Rewording scenarios 6/7 is out of scope for step 12.
- Every already-correct, ETAPA-I-clean statement in `README.md` /
  `CLAUDE.md` (seven-feature inventory, AWS-first framing, no removed
  adapters, real `boto3` S3) — additive edit only; not rewritten.

This change is strictly ROADMAP ETAPA I step 12 (the final ETAPA I step). It
adds no AWS code, claims no unshipped AWS adapter, and changes no runtime
behavior.
