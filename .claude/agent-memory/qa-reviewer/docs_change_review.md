---
name: docs-change-review
description: Gotchas when reviewing _template scaffold-removal / docs-only / ROADMAP-ETAPA-I removal changes
metadata:
  type: project
---

ROADMAP ETAPA I is a multi-step cleanup making the AWS-first starter "honest":
purging the deleted in-tree `_template` scaffold, then removing non-AWS backends
(step 3 = SMTP email adapter, step 4 = Resend, etc.). Steps are deliberately
narrow; reviewers must reject scope creep into adjacent steps (Step 9 README
AWS-first tagline + feature matrix, Step 10 CLAUDE feature matrix, Step 11
docs/operations.md trim).

**Why:** the roadmap intentionally splits this into independent changes so each
stays small and reviewable.

**How to apply when reviewing these changes:**
- Preserved-on-purpose references (NOT defects if still present): email
  `EmailTemplateRegistry` / `register_template` / `docs/email.md`; the
  file-storage S3 "ships as scaffolding" note at `docs/file-storage.md:5`;
  CONTRIBUTING "scaffold a change with the OpenSpec workflow" (unrelated verb).
- `_template` survivors that are correctly LEFT ALONE in docs-only changes:
  `alembic.ini` `file_template` config; the historical migration files
  `alembic/versions/20260511_0008_template_things_table.py` and
  `20260514_0011_drop_template_things.py` (migration history of the removed
  feature's `things` table — touching `alembic/` violates docs-only scope).
- Pre-existing doc inconsistencies out of scope here: README "What's New" says
  `auth` split into 2 features; CLAUDE says "Six features"; CONTRIBUTING says
  "Seven features". Note as non-blocking only unless the change's own scope
  covers it.
- `CONTRIBUTING.md` is NOT always listed in proposal/tasks scope but legitimately
  needs edits when it links a deleted doc — the repo-wide-audit task covers
  "purge any straggler". Flag as a scope-doc gap (Suggestion), not a Critical.
- README links to CLAUDE headings via GitHub slug anchors
  (`CLAUDE.md#adding-a-new-feature` ↔ `## Adding a new feature`). Verify the
  target heading exists.

**Backend-removal (step 3+) review recipe — worked on remove-smtp-adapter:**
- The single accepted `smtp` survivor is the arbitrary `DeliveryError(reason=
  "smtp 550")` string literal in
  `src/features/email/tests/unit/test_send_email_job_log_redaction.py` — NOT a
  defect, the proposal explicitly leaves it (cosmetic rename is opt-in).
- Email backend has THREE `EmailSettings.from_app_settings(...)` call sites that
  must move in lockstep: `src/main.py`, `src/worker.py`,
  `src/cli/create_super_admin.py`. Plus two test fixtures repointed off the
  removed backend: `src/features/authentication/tests/e2e/conftest.py` and
  `src/app_platform/tests/unit/observability/test_configure_tracing.py`.
- `src/app_platform/tests/test_settings.py` has a shared `_VALID_PROD_ENV` dict
  many prod tests depend on — when a backend is removed it must be repointed to
  a still-valid backend (smtp→resend) or every prod test breaks.
- The email contract suite `test_email_port_contract.py` is parametrized over
  `[console, fake, resend]` only (ids likewise) — never SMTP — so backend
  removal needs no contract-test edit; it stays green automatically.
- pydantic-settings ignores unknown env vars by default (no `extra="forbid"`),
  so removed `APP_EMAIL_SMTP_*` keys in a leftover `.env` are silently dropped —
  not a startup break.
- When `validate()` had multiple `missing: list[str]` reuses, removing the
  first branch requires re-annotating the survivor as `missing: list[str] = []`
  (was a bare reassignment) — mypy catches this if missed.
