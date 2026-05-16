---
name: project-roadmap-etapa-i
description: ROADMAP ETAPA I systematically removes non-AWS production-shaped adapters from this AWS-first starter; production-with-X is intentionally not bootable until the AWS adapter lands
metadata:
  type: project
---

This starter is AWS-first. ROADMAP ETAPA I ("dejar el repo honesto")
removes non-AWS production-shaped adapters one change at a time:
SMTP (step 3, done), Resend email (step 4, done), and arq/SpiceDB/S3
in later steps. Dev-only adapters (`console` email, `in_process` jobs)
are kept. Real AWS adapters (e.g. `aws_ses`) arrive at ROADMAP step 25.

**Why:** norte is "una sola opción opinada > tres opciones a medias".
A production validator that refuses to boot (e.g. email refuses
`console` in production with no accepted alternative) is the *honest*
mid-cleanup state — it is preferred over relaxing the refusal, which
would silently black-hole transactional mail in prod.

**How to apply:** when implementing an ETAPA I removal change: keep
production-refusal validators as refusals (only reword messages to
drop the removed backend name); do NOT add the future AWS adapter or
relax the refusal; docs get Resend/SMTP/etc. lines removed only (no
wholesale rewrite — later ROADMAP steps own README/CLAUDE/operations
narrative rewrites). Audits in the spec proposal can be slightly off
on doc-only files (e.g. `CONTRIBUTING.md` pre-deploy checklist) —
re-verify greps yourself and flag conflicts rather than silently
editing out-of-scope files.
