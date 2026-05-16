---
name: openspec-workflow
description: How OpenSpec changes are structured and validated in this repo
metadata:
  type: reference
---

OpenSpec changes live in `openspec/changes/<change-name>/` with `proposal.md`,
`tasks.md`, and `specs/<capability>/spec.md` delta files. Canonical specs live
in `openspec/specs/<capability>/spec.md`.

- Validate a change: `openspec validate <change-name> --strict` (run from repo root).
- `--strict` requires every change to carry at least one delta operation; a
  zero-delta docs-only change fails strict. The team's workaround is to ship a
  `## MODIFIED Requirements` delta that re-states an existing requirement
  verbatim plus an ADDED scenario (see `remove-template-feature` and
  `remove-template-scaffold-docs`).
- For a MODIFIED delta to apply cleanly on archive, the `### Requirement: <name>`
  must exactly match a requirement name in the canonical
  `openspec/specs/<capability>/spec.md`. Verify by grepping
  `^### Requirement:` in the canonical file.
- Archive: `openspec archive <change-name>` — pass `--skip-specs` ONLY for true
  zero-delta changes; changes carrying a spec delta must archive WITHOUT it.
