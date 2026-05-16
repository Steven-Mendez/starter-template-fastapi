# QA Reviewer Memory — starter-template-fastapi

- [OpenSpec workflow](openspec_workflow.md) — changes live in openspec/changes/<name>/; validate with `openspec validate <name> --strict`; zero-delta changes fail strict
- [Docs-change review tips](docs_change_review.md) — recurring "purge _template scaffold-recovery" cleanup; preserved exceptions and gotchas
- [Spec-delta capability targeting](spec_delta_capability_targeting.md) — MODIFIED/REMOVED deltas must sit in the capability dir that owns the requirement; --strict does NOT catch a misfile; grep every base spec
