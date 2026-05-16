---
name: openspec-removed-block-form
description: A `## REMOVED Requirements` delta entry is header + **Reason:** prose only — no restated SHALL/scenarios; --strict accepts this and it archives by deleting the base requirement
metadata:
  type: project
---

In an OpenSpec spec delta, a `## REMOVED Requirements` entry is
correctly just the `### Requirement: <verbatim header>` plus a
`**Reason:**` paragraph. It does NOT restate the SHALL text or carry
scenarios forward (unlike `## MODIFIED`). `openspec validate --strict`
accepts this form, and archive deletes the matching base requirement.

**Why:** Seen in `remove-spicedb-stub` (ROADMAP ETAPA I step 6): the
`SpiceDB adapter is a structural placeholder` requirement was removed
with header + reason only; `--strict` passed and the header
byte-matched `openspec/specs/authorization/spec.md`. Do not flag a
reason-only REMOVED block as "missing scenarios" — that is the spec.

**How to apply:** For REMOVED entries, verify (1) the header
byte-matches a base requirement in the *delta's own* capability dir
(see [[spec-delta-capability-targeting]]), (2) a `**Reason:**` is
present. For MODIFIED entries in the same change, still verify the
restated SHALL is byte-diffed against base so only the intended clause
changed and every scenario is carried forward verbatim.
