---
name: roadmap-workflow
description: Repo uses OpenSpec; work is driven by ROADMAP.md one-step-per-change, strict order, no step-mixing per PR
metadata:
  type: project
---

This repo's spec convention is **OpenSpec** (`openspec/` with `changes/`, `specs/`, `config.yaml`). Archived changes live in `openspec/changes/archive/`.

Work is driven by `ROADMAP.md` at repo root (AWS-first FastAPI starter).

**Why:** The user maintains an explicit, ordered roadmap (Etapas I–X, steps 1–56). It encodes already-made decisions not to re-litigate (AWS-only prod target, keep dev-only adapters, remove non-AWS production adapters, Cognito federates with local auth = "Opción B").

**How to apply:**
- The user opens a session with *"Vamos por el paso N del ROADMAP"*. Then: launch `spec-writer` scoped to exactly that step → wait for user approval → `test-engineer` → `implementer` → `qa-reviewer`.
- One roadmap step = one OpenSpec change = one PR. Never mix steps in a PR. If a step is too big, split into sub-steps but keep strict order.
- Mark `[x]` in `ROADMAP.md` and update the progress checklist table when a step closes.
- Etapa I (steps 1–12) is cleanup/honesty work: the `_template` feature code is already removed from `src/features/`, but docs (`CLAUDE.md`, `README.md`, `docs/feature-template.md`, `docs/architecture.md`) still reference it — step 1 purges those references.
