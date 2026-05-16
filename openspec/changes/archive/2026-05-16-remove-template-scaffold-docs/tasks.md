## 1. README.md — remove scaffold-recovery references

- [x] 1.1 Rewrite the intro paragraph (~lines 9–14). Remove "The intended first
      move on a new project is **clone, recover the scaffold from git history,
      run**." and the sentences about the removed in-tree `_template` feature
      and restoring it from the pre-removal commit. Replace with a sentence
      that frames the first move as: clone, then build your first feature
      from scratch following the documented hexagonal layout. Do NOT alter
      the surrounding production-shaped-starter description or introduce an
      AWS-first tagline (that is ROADMAP Step 9).
- [x] 1.2 In the "What's New" section (~lines 23–25), delete the sentence
      "The `remove-template-feature` change then removed the in-tree
      `_template` scaffold; see its directory under … for the rationale."
      Leave the `starter-template-foundation` description intact.
- [x] 1.3 In the "Documentation" list (~lines 45–47), delete the
      `- [Feature Template Guide](docs/feature-template.md) — recovering the
      scaffold from git history and the "copy and rename" workflow for new
      features.` bullet entirely (the linked file is being deleted).
- [x] 1.4 In "Starting A New Project" (~lines 141–157), replace step 2 and
      step 3 so they no longer say "Recover the feature scaffold from git
      history (`git checkout <pre-removal-sha>^ -- src/features/_template`)"
      and no longer link `docs/feature-template.md`. Reword to: create
      `src/features/<your-feature>/` with the `domain/ application/ adapters/
      composition/ tests/` layout and follow the "Adding a new feature"
      steps in `CLAUDE.md`. Keep steps 1, 4, and 5 (clone/rename remote,
      register with the authorization registry, generate the Alembic
      revision) and the closing paragraph as-is.
- [x] 1.5 After editing, grep `README.md` for `_template`, `feature-template`,
      `pre-removal`, and "scaffold" to confirm no scaffold-recovery reference
      survives. The only acceptable remaining "template" hits are the project
      name `starter-template-fastapi` and unrelated prose; there must be zero
      `_template` / git-history-recovery references.

## 2. CLAUDE.md — remove scaffold-recovery references

- [x] 2.1 In the architecture intro (~lines 50–51), remove the sentence
      "The previous in-tree `_template` scaffold has been removed — copy from
      git history when starting a new feature." Rephrase the surrounding text
      so it still states that six features ship out of the box without
      referencing the removed scaffold or git-history recovery.
- [x] 2.2 Delete the entire `### Scaffold for new features` section
      (~lines 169–177), including the heading and the
      `git checkout <pre-removal-sha>^ -- src/features/_template` instructions.
- [x] 2.3 In the "Adding a new feature" numbered list, rewrite step 1
      (~line 214). Replace "Recover the scaffold from git history
      (`git checkout <pre-removal-sha>^ -- src/features/_template`), then move
      it to `src/features/<name>/` and rename the entity, table, routes, and
      tests inside the copy." with: create `src/features/<name>/` from
      scratch following the layer stack (`domain → application → adapters →
      composition`) and the per-feature conventions documented above; add the
      entity, table, routes, and tests. Keep steps 2–10 unchanged.
- [x] 2.4 In the "Coding conventions" bullets, rewrite the bullet at
      ~line 242. Replace "New feature code goes under
      `src/features/<feature_name>/` mirroring the scaffold recovered from git
      history (see \"Adding a new feature\")." with: New feature code goes
      under `src/features/<feature_name>/` following the layer stack and the
      "Adding a new feature" steps above. Do not reference git-history
      recovery.
- [x] 2.5 Do NOT modify the feature matrix table, the "Production checklist",
      the env-var tables, or any other CLAUDE.md content — those are out of
      scope for Step 1 (Step 10 owns the matrix re-framing).
- [x] 2.6 After editing, grep `CLAUDE.md` for `_template`, `feature-template`,
      `pre-removal`, and `scaffold`. Confirm zero `_template` /
      scaffold-recovery references remain. The `EmailTemplateRegistry` /
      `register_template` mentions (~lines 118, 148) MUST remain — they are
      unrelated and in-scope to preserve.

## 3. docs/architecture.md — remove scaffold-recovery reference

- [x] 3.1 Rewrite the sentence at ~lines 13–14 ("so adding a new feature is a
      copy-and-rename of the scaffold recovered from git history (see
      [Feature Template Guide](feature-template.md))."). Replace with: so
      adding a new feature means creating that same
      `domain/ application/ adapters/ composition/ tests/` layout by hand and
      wiring it through the authorization/email/jobs registries. Remove the
      `feature-template.md` link entirely (the file is being deleted).
- [x] 3.2 Grep `docs/architecture.md` for `_template`, `feature-template`, and
      `scaffold` to confirm no scaffold-recovery reference remains.

## 4. docs/development.md — remove scaffold-recovery reference

- [x] 4.1 Rewrite the "New feature" table row at line 203. Replace "Recover
      the scaffold from git history and follow
      [Feature Template Guide](feature-template.md)." with a cell pointing at
      the "Adding a new feature" steps in `CLAUDE.md` and the
      `src/features/<feature>/` layout — no git-history recovery, no
      `feature-template.md` link.
- [x] 4.2 Grep `docs/development.md` for `_template`, `feature-template`, and
      "recover the scaffold" to confirm no scaffold-recovery reference
      remains.

## 5. Delete docs/feature-template.md

- [x] 5.1 Delete the file `docs/feature-template.md` in its entirety.
- [x] 5.2 Repo-wide grep for any remaining link to `feature-template.md`
      (e.g. `grep -rn "feature-template" .` excluding `.git/` and the
      `openspec/changes/archive/` history). Every live link must have been
      removed by tasks 1–4; fix any straggler this surfaces.

## 5b. CONTRIBUTING.md — remove broken documentation-index link

- [x] 5b.1 In `CONTRIBUTING.md` (~line 40), delete the documentation-index
      row that links the now-deleted `docs/feature-template.md`. No other
      `CONTRIBUTING.md` content is touched.

## 6. Repo-wide audit (the ROADMAP says "de todo")

- [x] 6.1 Run `grep -rn -e "_template" -e "feature-template" -e "recover the
      scaffold" -e "scaffold from git history" -e "pre-removal-sha" .`
      excluding `.git/`, `openspec/changes/archive/`, and the
      `openspec/changes/remove-template-scaffold-docs/` change itself.
- [x] 6.2 For every hit outside the explicitly-preserved set, purge the
      `_template` / scaffold-recovery reference following the same
      "build from scratch" framing.
- [x] 6.3 Confirm the explicitly-preserved references are still present and
      untouched: `EmailTemplateRegistry` / `register_template` and
      `docs/email.md`; the file-storage S3 "ships as scaffolding" note at
      `docs/file-storage.md:5`. These are unrelated uses of
      "template"/"scaffold" and MUST NOT be removed.

## 7. Wrap-up

- [x] 7.1 No source code, settings, migrations, or behavior tests changed —
      this is documentation-only. Confirm `git status` shows only doc files
      (`README.md`, `CLAUDE.md`, `docs/architecture.md`,
      `docs/development.md`, deleted `docs/feature-template.md`) plus the
      OpenSpec change directory.
- [x] 7.2 Run `openspec validate remove-template-scaffold-docs --strict` and
      confirm it passes.
- [x] 7.3 Confirm the deleted `docs/feature-template.md` and the four edited
      doc files satisfy the new `project-layout` →
      "Documentation reflects the new layout" scenario
      ("Docs do not instruct recovering the removed scaffold").
- [ ] 7.4 Archive with `openspec archive remove-template-scaffold-docs`
      (do NOT pass `--skip-specs` — this change carries a `project-layout`
      spec delta; see the SPEC-DELTA DECISION note in the proposal).
