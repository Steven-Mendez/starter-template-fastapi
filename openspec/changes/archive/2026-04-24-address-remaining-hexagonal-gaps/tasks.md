## 1. Aggregate Consistency Hardening

- [x] 1.1 Add explicit aggregate behavior for deleting a column with contiguous reindexing of remaining columns.
- [x] 1.2 Refactor command handler delete-column flow to call aggregate behavior and remove `hasattr`/missing-method fallback.
- [x] 1.3 Add/adjust unit tests to assert no position gaps after deleting middle columns.

## 2. Domain Encapsulation Refinement

- [x] 2.1 Remove aggregate-to-child private method calls (underscore methods) from domain model interactions.
- [x] 2.2 Add tests or static architecture checks that reject private cross-entity API coupling in domain aggregate logic.

## 3. Architecture Governance Coverage Expansion

- [x] 3.1 Extend boundary tests to inspect FastAPI dependency graphs and fail if routes depend on container provider callables directly.
- [x] 3.2 Extend import-governance checks to catch both `from ... import ...` and `import ... as ...` bypass styles for concrete handler dependencies.

## 4. OpenSpec Catalog Integrity

- [x] 4.1 Normalize legacy specs that currently fail `openspec validate --all` by adding canonical `## Purpose` and `## Requirements` structure.
- [x] 4.2 Remove placeholder `Purpose` text (e.g., `TBD`) from main specs and replace with concrete intent.
- [x] 4.3 Run `openspec validate --all` and keep the catalog green.
