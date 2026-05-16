# Tasks — document-src-cli (ROADMAP ETAPA I step 12, final ETAPA I step)

## Phase 0 — Verification gate (do this BEFORE writing any doc prose)

Every command string, subcommand, flag, default, exit code, and `APP_*` env
var that lands in `README.md` / `CLAUDE.md` MUST be re-derived from the code
and the `Makefile`. Do not trust the module docstrings — where they differ
from the live `Makefile`/`CLAUDE.md` convention, **the code/Makefile wins**.

- [x] Read `src/cli/__init__.py` and confirm the package is a project-level
      composition root that features MUST NOT import; confirm the Import
      Linter contract name `Features do not import the CLI composition root`
      in `pyproject.toml` (`:657–672`, `forbidden_modules = ["cli"]`).
- [x] Read `src/cli/create_super_admin.py` and confirm, verbatim from the
      `argparse` block (`:224–241`):
  - [x] required subparser, `dest="command"`, `required=True`
  - [x] subcommand name is exactly **`create-super-admin`** (`:230`)
  - [x] `--email` is **required** (`:236`)
  - [x] `--password-env` exists with `default="AUTH_BOOTSTRAP_PASSWORD"`
        (`:237`)
  - [x] password is read via `os.getenv(password_env)` (`:183`) and a
        missing/empty value raises
        `SystemExit("Environment variable <NAME> is required")` (`:184–185`)
  - [x] `BootstrapRefusedExistingUserError` / `BootstrapPasswordMismatchError`
        exit code `2` (`:206`, `:214`)
  - [x] all `APP_*` config is read through `AppSettings()` (`:93`)
  - [x] there is **no** `make` target for it (`grep -n create.super
        Makefile` returns nothing) — it is invoked directly
- [x] Read `src/cli/outbox_prune.py` and confirm:
  - [x] `main(argv)` ignores `argv` (`:76`, `# noqa: ARG001`) → `run_once()`;
        **no subcommand, no flag**
  - [x] retention/batch from `OutboxSettings.from_app_settings(AppSettings())`
        (`:39–40`) i.e. the `APP_OUTBOX_*` settings
  - [x] `APP_OUTBOX_ENABLED` is **intentionally not consulted**
        (docstring `:17–21`)
  - [x] exit `0` on success, `1` on `Err` (`:64–65`, `:73`)
- [x] Read `Makefile` and confirm `outbox-prune` target
      (`:27–28` = `PYTHONPATH=src uv run python -m cli.outbox_prune`) and the
      `PYTHONPATH=src uv run python -m <module>` convention used by
      `dev`/`worker`/`outbox-retry-failed`/`outbox-prune`.
- [x] Record the docstring-vs-Makefile discrepancy: both module docstrings
      (`create_super_admin.py:15–19`, `outbox_prune.py:14`) show
      `uv run python -m …` **without** `PYTHONPATH=src`; the live
      `Makefile`/`CLAUDE.md` convention includes it. **Documented invocation
      uses `PYTHONPATH=src` (Makefile wins). Do NOT edit the docstrings.**
- [x] Confirm no removed-adapter name (`_template`, `smtp`, `resend`, `arq`,
      `spicedb`/SpiceDB) and no "S3 stub"/`NotImplementedError` S3 wording is
      introduced by the new prose (ETAPA I steps 1–11 non-regression).

## Phase 1 — README.md (prose + table voice)

- [x] Add a new `## Operational Commands` section, placed **after**
      `## Common Commands` (section currently ends at `README.md:322`) and
      **before** `## Troubleshooting` (`:324`). It belongs with the
      command-catalogue content; the `make`-target table at `:305–322` cannot
      carry the "when to use / which env vars" semantics, so this is a
      dedicated subsection.
- [x] Document **create or promote the first system admin**:
  - exact invocation:
    `PYTHONPATH=src uv run python -m cli.create_super_admin create-super-admin --email <email> --password-env <ENVVAR>`
  - what it is: a project-level composition-root CLI (peer of `main.py` /
    `worker.py`) that creates or promotes the first `system:main#admin`
  - when to use it: to bootstrap the very first admin when no admin (and thus
    no admin JWT) exists yet — the **on-demand alternative** to the
    `APP_AUTH_SEED_ON_STARTUP` /
    `APP_AUTH_BOOTSTRAP_SUPER_ADMIN_EMAIL/PASSWORD` startup-bootstrap path
    (cross-reference the operations/auth docs; do **not** contradict them)
  - key env / flags: `--email` required; `--password-env` defaults to
    `AUTH_BOOTSTRAP_PASSWORD` and names the env var holding the password
    (kept out of shell history / process listings); a missing value aborts;
    `APP_*` configure DB/auth via `AppSettings`; promoting an **existing**
    account requires `APP_AUTH_BOOTSTRAP_PROMOTE_EXISTING=true` plus the
    account's real password (default-deny — non-zero exit otherwise)
- [x] Document **prune the outbox once**:
  - exact invocation: `make outbox-prune` (equivalently
    `PYTHONPATH=src uv run python -m cli.outbox_prune`); **no flags**
  - what it is: one-shot prune of terminal (`delivered`/`failed`) outbox rows
    and stale dedup marks, in batches; **same `PruneOutbox` code path** as the
    worker's hourly prune cron (operator and scheduled prunes cannot drift)
  - when to use it: an on-demand sweep without waiting for the worker cron
  - key env: retention/batch from the `APP_OUTBOX_*` settings;
    `APP_OUTBOX_ENABLED` is **intentionally ignored** (the operator already
    decided to prune)
- [x] Keep it tight; summarise — do **not** paste the module docstrings.
      Match the README's existing prose-plus-table voice.
- [x] Verify no ETAPA I step 1–11 content regressed (seven-feature inventory,
      AWS-first framing, no removed adapters, real `boto3` S3) — additive
      edit only.

## Phase 2 — CLAUDE.md (terse command-block voice)

- [x] Inside the existing fenced `bash` block in `## Commands`
      (`CLAUDE.md:7–45`), add a new `# Operational CLI` group **after** the
      `# Migrations` group (`:35–37`) and **before** `# Run single test file`
      (`:39`), matching the file's one-line-`# comment` command style:
  - [x] `PYTHONPATH=src uv run python -m cli.create_super_admin create-super-admin --email <e> --password-env <ENVVAR>`
        with a terse comment noting it creates/promotes the first
        `system:main#admin` and is the on-demand alternative to the
        `APP_AUTH_SEED_ON_STARTUP` bootstrap
  - [x] `make outbox-prune` with a terse comment noting one-shot prune of
        terminal outbox rows + stale dedup marks, same code path as the
        worker prune cron, ignores `APP_OUTBOX_ENABLED`
- [x] Do **not** contradict the existing startup-bootstrap documentation in
      `CLAUDE.md`'s Authentication-feature section and the Key-env-vars
      tables (`APP_AUTH_SEED_ON_STARTUP`,
      `APP_AUTH_BOOTSTRAP_SUPER_ADMIN_EMAIL/PASSWORD`,
      `APP_AUTH_BOOTSTRAP_PROMOTE_EXISTING`) — present the CLI as the explicit
      alternative to that startup path.
- [x] Summarise — do not paste the module docstrings. Keep the terse style.
- [x] Verify no ETAPA I step 1–11 `CLAUDE.md` content regressed
      (seven-feature matrix, AWS-first framing, no removed adapters, real
      `boto3` S3, production-checklist) — additive edit only.

## Phase 3 — Spec delta (project-layout, verbatim restatement + 1 ADDED scenario)

- [x] **At implement time, re-read the CANONICAL
      `openspec/specs/project-layout/spec.md` "Documentation reflects the new
      layout" block** (header byte-match; currently `spec.md:93`) and copy it
      **verbatim** into this change's `specs/project-layout/spec.md` under
      `## MODIFIED Requirements`: all four SHALL paragraphs and all eight
      existing scenarios, unchanged. The drafted delta mirrors the canonical
      block as read during drafting (4 paragraphs + 8 scenarios incl. step
      11's operations.md scenario). If steps 7/11 (or any other in-flight
      project-layout change) refined the canonical block since, **re-copy the
      then-current canonical text** so the restatement still byte-matches and
      no prior refinement is dropped.
- [x] Append exactly **one** new scenario,
      `#### Scenario: README.md and CLAUDE.md document the src/cli/ operational commands`,
      asserting both docs carry an accurate, code-true CLI / operational-
      commands section for both commands (exact invocation, when to use, key
      env vars), per the drafted delta. Do **not** rewrite carried scenarios
      6/7 (their "no `src/cli/` section" sub-clauses are carried byte-for-byte
      and become narrowly stale by design — out of scope to reword here).
- [x] `openspec validate document-src-cli --strict` passes (>=1 delta op;
      verbatim restatement byte-matches the canonical header and text).
- [x] Archive **WITHOUT** `--skip-specs`
      (`openspec archive document-src-cli`) so the ADDED scenario folds into
      the canonical `project-layout` spec.

## Phase 4 — ROADMAP close-out (implementer/orchestrator at implement/archive; NOT the spec-writer now)

- [x] Flip `ROADMAP.md:58` step 12 `- [x]` → `- [x]`.
- [x] Update the bottom progress-checklist table: change the row
      `| I — Limpieza | 1–12 | Pendiente |` →
      `| I — Limpieza | 1–12 | Completado |` (ETAPA I fully closed — step 12
      is the final ETAPA I step).
- [x] Confirm both ROADMAP edits are in the same implement/archive change as
      the doc edits; this proposal does not perform them.

## Phase 5 — Final audit

- [x] `grep -n 'cli\.' README.md CLAUDE.md` shows the new sections with the
      verified invocations (`PYTHONPATH=src` present; subcommand
      `create-super-admin`; `--email`/`--password-env`; `make outbox-prune`).
- [x] No invented flag, subcommand, or env var appears (cross-check against
      the Phase 0 findings).
- [x] No removed-adapter name (`_template`/SMTP/Resend/arq/SpiceDB) and no
      "S3 stub" wording introduced.
- [x] Only `README.md`, `CLAUDE.md`, and the OpenSpec artifacts changed
      (plus the Phase-4 `ROADMAP.md` edits at implement time); no `docs/`,
      no code, no `Makefile`, no test, no migration, no env var, no docstring
      change.
