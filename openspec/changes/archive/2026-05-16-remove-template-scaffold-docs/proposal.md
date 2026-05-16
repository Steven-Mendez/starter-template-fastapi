## Why

The in-tree `_template` feature was deleted by the `remove-template-feature`
change (archived 2026-05-12). That change deliberately left the scaffolding
*concept* alive in the docs by pointing readers at git history
(`git checkout <pre-removal-sha>^ -- src/features/_template`) and a dedicated
`docs/feature-template.md` guide.

ROADMAP ETAPA I, Step 1 reverses that decision: *"Eliminar el scaffold
`_template` de todo … No documentarlo, no recuperarlo de git history."* The
"recover the scaffold from git history" workflow is now considered noise — it
sends new operators chasing a deleted directory and a SHA that drifts further
out of reach with every commit, instead of teaching the hexagonal conventions
the repo already documents in `CLAUDE.md`. Keeping the repo honest means the
docs should describe building a feature from scratch against the existing
layer/registry rules, not recovering a ghost.

This is the first step of a longer cleanup. It is intentionally narrow: it only
removes `_template` / scaffold-recovery references. It does not touch the
AWS-first README tagline (Step 9), the CLAUDE.md feature-matrix re-framing
(Step 10), or `docs/operations.md` (Step 11) — those are separate roadmap
steps with their own changes.

## What Changes

- Rewrite the `README.md` references that describe the workflow as "clone,
  recover the scaffold from git history, run" (intro paragraph ~9–14, the
  "What's New" `_template` sentence ~23–25, the `Feature Template Guide`
  documentation-index bullet ~45–47, and the "Starting A New Project" steps
  ~144–149) so they describe creating a feature from scratch following the
  documented hexagonal conventions. Do not rewrite the AWS-first tagline or
  the feature-inventory matrix — those are out of scope (Step 9).
- Rewrite `CLAUDE.md` to drop the entire `### Scaffold for new features`
  section (~170–177), restate the "Adding a new feature" step 1 (~214) as
  "create the feature directory from scratch following the layer stack and
  registries documented above" instead of "recover the scaffold from git
  history", and drop the "mirroring the scaffold recovered from git history"
  clause from the coding-conventions bullet (~242). Leave the feature matrix,
  production checklist, and all other CLAUDE.md content unchanged (Step 10
  owns the matrix re-framing).
- Rewrite `docs/architecture.md` ~13–14 so the "adding a new feature" sentence
  no longer says "a copy-and-rename of the scaffold recovered from git
  history" and no longer links `feature-template.md`; describe it as building
  the standard `domain/ application/ adapters/ composition/ tests/` layout by
  hand.
- Rewrite `docs/development.md:203` ("New feature") so the table cell no longer
  says "Recover the scaffold from git history" and no longer links
  `feature-template.md`; point at the "Adding a new feature" guidance in
  `CLAUDE.md` instead.
- Delete `docs/feature-template.md` entirely.
- Verify no other doc retains a `_template`, `feature-template.md`, or
  "recover the scaffold from git history" reference, and purge any that the
  audit surfaces.

Explicitly preserved (NOT in scope, must stay): unrelated uses of the words
"template" and "scaffold" — the email `EmailTemplateRegistry` /
`register_template` API and `docs/email.md`, the file-storage S3 "ships as
scaffolding" stub note at `docs/file-storage.md:5`, and every CLAUDE.md
production rule and feature-matrix row.

**Capabilities — Modified**
- `project-layout`: the existing "Documentation reflects the new layout"
  requirement gains a scenario forbidding scaffold-recovery instructions in
  the docs.

**Capabilities — New**
- None.

<!-- SPEC-DELTA DECISION (deviation from the original Step 1 brief, called out
     for the orchestrator):

     The brief assumed this would be a zero-delta, docs-only change archived
     with `--skip-specs`, on the reasoning that no requirement mentions
     `_template`. That reasoning is correct about `_template` specifically
     (grep of openspec/specs/project-layout/spec.md confirms zero hits for
     `_template` / `feature-template` / "scaffold from git history"), BUT
     `openspec validate --strict` requires every change to carry at least one
     delta operation. A zero-delta change fails strict validation
     ("must have at least one delta"); the directly-analogous prior change
     `remove-template-feature` (archived 2026-05-12) shipped a delta for the
     same reason.

     There IS an applicable existing requirement: `project-layout` →
     "Documentation reflects the new layout" already governs the content of
     `CLAUDE.md`, `README.md`, and `docs/*.md`. Forbidding scaffold-recovery
     instructions is a genuine refinement of that requirement, so this change
     ships a `## MODIFIED Requirements` delta that re-states that requirement
     verbatim plus one ADDED scenario. This makes `--strict` pass honestly
     instead of papering over a hard validator rule.

     Consequence for the orchestrator: archive WITHOUT `--skip-specs`
     (`openspec archive remove-template-scaffold-docs`) so the new scenario
     is folded into the canonical project-layout spec. -->

## Impact

- **Code**: none. No source, settings, migrations, or tests are touched. This
  is a documentation-only change.
- **Docs**: `README.md` (scaffold-recovery references only), `CLAUDE.md`
  (scaffold-recovery references only — the `### Scaffold for new features`
  section is deleted and the "Adding a new feature" step 1 + the
  coding-conventions bullet are reworded), `docs/architecture.md` (~13–14
  reworded, `feature-template.md` link removed), `docs/development.md` (line
  203 reworded, `feature-template.md` link removed), `CONTRIBUTING.md` (removed
  a broken documentation-index link to the deleted `docs/feature-template.md`),
  `docs/feature-template.md` (deleted).
- **Spec delta**: one `## MODIFIED Requirements` delta on the `project-layout`
  capability (`specs/project-layout/spec.md`) — re-states the existing
  "Documentation reflects the new layout" requirement verbatim and ADDs a
  scenario forbidding scaffold-recovery instructions. No requirement is
  removed and no behavior outside documentation content changes. Archive
  WITHOUT `--skip-specs` (see the SPEC-DELTA DECISION note above for why this
  deviates from the original brief).
- **Production**: none.
- **Scope boundary**: deliberately narrow. ROADMAP Steps 9 (README AWS-first
  tagline + feature-matrix rewrite), 10 (CLAUDE.md feature-matrix re-framing),
  and 11 (`docs/operations.md` trim) are explicitly NOT addressed here and
  remain open. Reviewers should reject any edit in this change that touches
  content beyond `_template` / scaffold-recovery removal.
- **Backwards compatibility**: no behavior change. Readers who previously
  followed the git-history recovery workflow will instead find the
  build-from-scratch guidance; the deleted feature remains in git history for
  anyone who deliberately goes looking, but the docs no longer instruct it.
