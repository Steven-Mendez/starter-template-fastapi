# QA Reviewer Memory — starter-template-fastapi

- [OpenSpec workflow](openspec_workflow.md) — changes live in openspec/changes/<name>/; validate with `openspec validate <name> --strict`; zero-delta changes fail strict
- [Docs-change review tips](docs_change_review.md) — recurring "purge _template scaffold-recovery" cleanup; preserved exceptions and gotchas
- [Spec-delta capability targeting](spec_delta_capability_targeting.md) — MODIFIED/REMOVED deltas must sit in the capability dir that owns the requirement; --strict does NOT catch a misfile; grep every base spec
- [OpenSpec REMOVED-block form](openspec_removed_block_form.md) — REMOVED entry = header + **Reason:** only (no SHALL/scenarios); valid under --strict; don't flag as "missing scenarios"
- [API doc-accuracy review](api_doc_accuracy_review.md) — recipe for QA-ing docs/api.md rewrites vs real inbound HTTP layer: 22-route inventory, operationId/schema gotchas, scope guards
- [S3 stub-drift false premise](s3_stub_drift_false_premise.md) — ROADMAP step 7 had a false premise; S3 adapter is real boto3, RETAINED (Option A); step 7 = wording-only 5-site drift fix
