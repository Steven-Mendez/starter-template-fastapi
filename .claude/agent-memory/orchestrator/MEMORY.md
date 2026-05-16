# Orchestrator Memory

- [Roadmap workflow](project_roadmap_workflow.md) — OpenSpec repo, ROADMAP.md drives work one-step-per-change in strict order, no step-mixing per PR
- [Push blocked in env](project_push_blocked_env.md) — github.com push fails in sandbox; use stacked per-step branches, don't retry pushes, user pushes at end
- [Step 7 S3 false premise](project_step7_s3_false_premise.md) — ROADMAP step 7 is wrong: S3 adapter is real working boto3 code, not a stub; do NOT delete it
