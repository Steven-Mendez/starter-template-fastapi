---
name: push-blocked-env
description: Git push to github.com is environmentally blocked in this sandbox; use stacked per-step branches, user pushes
metadata:
  type: project
---

In this sandboxed environment, `git push` to `origin` (github.com) **fails**: after a heavy pre-push hook runs the full local CI gate (quality, tests, security, migrations, docker — several minutes), the push itself dies with `Connection to github.com closed by remote host`. Network egress to github.com is blocked. `origin/main` observed stale (commits behind local) confirming pushes generally don't land here.

Also: direct `git push origin main` is denied by the Claude Code auto-mode classifier (wants PR-per-step, which matches ROADMAP "una PR por paso").

**Why:** Sandbox network policy + remote closing the connection; not a Claude Code permission toggle the user can flip.

**How to apply:**
- Do NOT burn cycles retrying pushes — each attempt wastes ~15 min on the pre-push CI gate before failing.
- Execute roadmap steps fully locally: spec → test → implement → qa → `openspec archive` → commit.
- Use **stacked per-step branches**: `roadmap/NN-<change-name>`, each branching from the previous step's branch, exactly one `<change>: implement & archive` commit per step. This preserves "one step = one PR" ([[roadmap-workflow]]).
- The pre-commit hook (end-of-file-fixer, trailing-whitespace, ruff) DOES run on commit and can modify staged files → re-`git add -A` and re-commit when it does. **Retry with plain `git add -A && git commit -m "$MSG"` — NEVER `--amend`.** If the first commit aborted (hook modified files, no commit created), an `--amend` retry will fold the changes into the *previous step's* commit and rename it, merging two steps into one (this happened once on step 3 and required a `git reset --soft` surgical split). The plain re-commit is idempotent: if the first attempt actually succeeded, the second prints "nothing to commit, working tree clean".
- At the end, hand the user the ordered branch list to push + open PRs themselves (they have working network).
- The repo's actual git history is direct linear commits to `main` (`<change>: implement & archive`, no PRs ever) — if the user later authorizes direct-to-main push, that matches established practice; absent that, stacked branches are the faithful fallback.
