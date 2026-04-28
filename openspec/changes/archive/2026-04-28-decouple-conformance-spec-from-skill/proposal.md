## Why

The two hex-conformance specs (`hexagonal-architecture-conformance` and `use-case-cohesion`) currently treat `.opencode/skills/fastapi-hexagonal-architecture/SKILL.md` as a normative artifact: requirements quote the skill as the canonical checklist, scenarios mandate diagnostic strings that name the skill, and one scenario asserts coverage of "the skill's `Review Checklist` section" via a meta-test that has since been deleted as conceptually wrong. This inverts the project's model: OpenSpec capabilities are the source of truth, the SKILL is descriptive support material for AI agents, and the architecture suite verifies the code against the specs. Architecture diagnostics already emit the prefix `hexagonal-architecture-conformance:` (the spec capability name), so the spec text now contradicts the implementation. This change realigns the specs with the principle that the SKILL is non-normative and removes the contradiction.

## What Changes

- Rewrite the "Automated Conformance Suite is the Source of Truth" requirement so it identifies *the spec capability itself* (not the SKILL) as the source the suite encodes, and remove the obsolete "Skill checklist coverage is complete" scenario whose enforcing meta-test was deleted.
- Rewrite the "Anti-Pattern Guards Applied to Application Classes" requirement to describe the anti-patterns directly (generic mega service objects, anemic pass-through use cases) rather than cite "anti-patterns listed in the SKILL".
- Replace the requirement "Conformance Diagnostics Reference the Skill" with "Conformance Diagnostics Reference the Spec Capability". The mandated diagnostic substring becomes `hexagonal-architecture-conformance:` (already what the suite emits).
- Rewrite the `use-case-cohesion` "One Use Case Per Business Intent" requirement so the "Aggregator service object is rejected" scenario cites the spec capability, not "Anti-Pattern 6 of the SKILL".
- **NON-BREAKING**: implementation already matches the new spec text (the test rename already landed). This change brings the specs into alignment.

## Capabilities

### New Capabilities
- None.

### Modified Capabilities
- `hexagonal-architecture-conformance`: Remove SKILL coupling from Source-of-Truth, Anti-Pattern Guard, and Diagnostic-Reference requirements; remove the obsolete checklist-coverage scenario.
- `use-case-cohesion`: Remove SKILL citation from the aggregator-service-object scenario.

## Impact

- Affected artifacts: `openspec/specs/hexagonal-architecture-conformance/spec.md`, `openspec/specs/use-case-cohesion/spec.md`.
- Affected code: none — the architecture suite already emits the new diagnostic prefix and the SKILL-coverage meta-test was already deleted.
- Affected docs: none required; existing references to the SKILL elsewhere (README, hex-design-guide) remain valid because they describe the skill as supporting material, not normative source.
- Long-term effect: the SKILL becomes purely descriptive; if the agent ecosystem changes (new skill format, replaced skill, removed entirely), no spec or test breaks. The OpenSpec capabilities remain the closed, terminal definition of conformance.
