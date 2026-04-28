## Context

Two specs in `openspec/specs/` reference `.opencode/skills/fastapi-hexagonal-architecture/SKILL.md` as if it were the normative source for hex-conformance. That inverts the intended model — OpenSpec capabilities are the source of truth and the SKILL is descriptive material for the AI agent. The architecture suite already emits `hexagonal-architecture-conformance:`-prefixed diagnostics, so the spec text is also out of sync with the implementation. This change updates the spec text to remove the SKILL coupling. There is no code or test change required.

## Goals / Non-Goals

**Goals:**
- Remove every load-bearing reference to the SKILL from `hexagonal-architecture-conformance` and `use-case-cohesion` specs.
- Make the diagnostic-prefix requirement match what the suite actually emits (`hexagonal-architecture-conformance:`).
- Drop the obsolete "Skill checklist coverage is complete" scenario whose enforcing meta-test no longer exists.

**Non-Goals:**
- Editing the SKILL itself; it remains valid as agent-facing material.
- Touching `README.md`, `hex-design-guide.md`, or other non-normative docs that mention the SKILL descriptively.
- Renaming the spec capability `hexagonal-architecture-conformance`. The capability id stays.

## Decisions

### Decision 1: Replace, do not rename, the diagnostic-reference requirement

The current requirement is named "Conformance Diagnostics Reference the Skill". The new behavior wants the name to be "Conformance Diagnostics Reference the Spec Capability" *and* changes the mandated substring inside the scenario. OpenSpec delta operations support `RENAMED Requirements` (name only) and `MODIFIED Requirements` (full content, header must match). A change that needs both rename and content edit fits cleanest as a `REMOVED Requirements` (old) plus `ADDED Requirements` (new) pair, with the REMOVED block carrying `**Reason**` and `**Migration**` fields.

**Alternative considered:** Keep the requirement name and just MODIFY the content. Rejected because the requirement title literally says "Reference the Skill" — leaving the title would be misleading even if the body no longer references the SKILL.

### Decision 2: MODIFY (not REMOVE) the source-of-truth requirement, dropping one scenario

"Automated Conformance Suite is the Source of Truth" stays as a requirement (the rule still holds), but the scenario "Skill checklist coverage is complete" is dropped (its enforcing meta-test was deleted as conceptually wrong). MODIFY copies the full updated requirement and replaces the prior block; the dropped scenario simply doesn't appear in the new content.

### Decision 3: MODIFY the anti-pattern requirement to describe anti-patterns directly

"Anti-Pattern Guards Applied to Application Classes" currently delegates the definition of "anti-patterns" to the SKILL. The new content names them inline: (1) generic service objects that aggregate multiple business intents on one class, and (2) anemic pass-through use cases. This makes the spec self-contained.

## Risks / Trade-offs

- **Risk: archiving merges deltas into main specs and breaks linkage to the previous archived change.** Mitigation: archived changes (`openspec/changes/archive/2026-04-28-hex-conformance-finalization/`) are immutable history; updating the main spec is the intended forward path. The archived change still describes the original intent at the time of merge.
- **Trade-off: REMOVED + ADDED loses the implicit "this requirement is the same one renamed" link.** Acceptable: the migration text in the REMOVED block points at the new requirement name, preserving traceability for humans reading the archive.
