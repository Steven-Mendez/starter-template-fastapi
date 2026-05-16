---
name: spec-delta-capability-targeting
description: OpenSpec MODIFIED/REMOVED deltas must live in the capability dir that actually owns the requirement; openspec validate --strict does NOT catch a misfiled requirement
metadata:
  type: feedback
---

When reviewing an OpenSpec change, for every `## MODIFIED Requirements`
and `## REMOVED Requirements` entry, grep the requirement's verbatim
header across **all** `openspec/specs/*/spec.md` files — not just the
capability the delta was filed under. The header must exist in the base
spec of the **same capability directory** the delta sits in, or archive
silently mis-applies (treats a MODIFIED as an effective ADDED and leaves
the real requirement, often still asserting deleted code, untouched).

**Why:** In `remove-arq-adapter`, the `Strategic \`Any\`/\`object\`
hotspots are typed` requirement actually lives in
`openspec/specs/quality-automation/spec.md`, but the change filed its
MODIFIED delta under `specs/project-layout/spec.md` (the design.md
spec-delta table asserted it was a project-layout requirement — it never
was). `openspec validate remove-arq-adapter --strict` passed anyway,
because strict validation checks each delta file's internal structure
(≥1 scenario, restated SHALL text), NOT cross-capability header
resolution. The misfile would have shipped a `quality-automation` spec
still mandating deleted `arq.WorkerSettings` / `Sequence[CronJob]` /
`build_relay_cron_jobs` symbols.

**How to apply:** Run, for each capability the change touches:
`for cap in <caps>; do grep -h '^### Requirement:' changes/<c>/specs/$cap/spec.md | while read h; do grep -qF "$h" openspec/specs/$cap/spec.md && echo OK || echo "MISS: $h"; done; done`
A MISS means either the header text drifted (fix the wording) or the
delta is in the wrong capability dir (move the whole `### Requirement:`
block to the correct `specs/<owning-cap>/spec.md`). Backtick-heavy
headers can false-MISS a naive shell grep — byte-compare with `od -c`
before trusting a single MISS, but never dismiss it without confirming
the header exists in *some* base spec under the *delta's own* capability.
