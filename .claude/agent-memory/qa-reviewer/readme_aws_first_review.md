---
name: readme-aws-first-review
description: Recipe for QA-ing the ROADMAP ETAPA I step 9 README AWS-first rewrite (readme-aws-first) and verifying its project-layout spec-delta byte-match
metadata:
  type: project
---

ROADMAP ETAPA I step 9 = `readme-aws-first`: rewrite `README.md` AWS-first,
code-true 7-feature inventory, discharge step-7's deferred `README.md:53`
S3-"stub" propagation. README-only change (+ openspec artifacts).

**Scope facts that look like gaps but are NOT defects:**
- Project-structure tree line keeps `src/platform/` (not `src/app_platform/`).
  Deliberately out of scope — proposal tasks 4.3 + scope boundary defer the
  `platform` on-disk-label question to step 1's already-satisfied scenario.
  Tree edits are limited to the `outbox` row + the `worker.py` comment.
- `KANBAN_SKIP_TESTCONTAINERS` env-var name left as-is (renaming = code change,
  out of scope). It is a real testcontainers skip flag, unrelated to Kanban.
- Remaining "scaffold" hits in README are all the *worker scaffold* / *feature
  unwired by any consumer* carve-out the project-layout spec explicitly
  preserves — not scaffold-RECOVERY prose. Zero recovery prose is the bar.

**Spec-delta byte-match (the critical check):** the change ships ONE
`## MODIFIED Requirements` op on project-layout "Documentation reflects the
new layout". By step 9, step 7 (`fix-s3-stub-drift`) has already archived
(commit 223b7dc), so canonical block = lines 93–135 of
`openspec/specs/project-layout/spec.md` (4 SHALL paras incl. step-7's S3
para at 99 + api.md para at 101; 5 scenarios incl. "No documentation
describes the real S3 adapter as a stub" at 130). Verify by:
`diff <(sed -n '93,135p' openspec/specs/project-layout/spec.md) \
      <(sed -n '3,45p' openspec/changes/readme-aws-first/specs/project-layout/spec.md)`
→ must be IDENTICAL. Delta then adds exactly ONE new scenario "README
presents the AWS-first framing and a code-true feature inventory" (scenario
count: canonical 5 → delta 6). `--strict` does NOT catch a byte mismatch or
a dropped step-7 refinement — must diff manually.

**Proof gate:** `make quality` green (22 import-linter contracts, mypy 479
files) proves zero code touched. `openspec validate readme-aws-first
--strict` → valid. `git diff --name-only` → only README.md (+ ignored
agent-memory + untracked openspec/changes/readme-aws-first/).

Outcome 2026-05-16: APPROVED, zero findings, all 5 acceptance criteria met.
