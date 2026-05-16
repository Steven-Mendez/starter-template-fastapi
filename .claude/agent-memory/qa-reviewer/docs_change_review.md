---
name: docs-change-review
description: Gotchas when reviewing _template scaffold-removal / docs-only changes
metadata:
  type: project
---

ROADMAP ETAPA I is a multi-step docs cleanup purging the deleted in-tree
`_template` scaffold and "recover from git history" workflow. Steps are
deliberately narrow; reviewers must reject scope creep into adjacent steps
(Step 9 README AWS-first tagline + feature matrix, Step 10 CLAUDE feature
matrix, Step 11 docs/operations.md trim).

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
