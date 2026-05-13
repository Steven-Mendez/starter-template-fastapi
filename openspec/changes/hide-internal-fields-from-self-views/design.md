## Context

Internal counters belong in admin views, not self views. The split is a tiny schema change with a measurable info-leak fix.

## Decisions

- **Two schemas, not one schema + dynamic include/exclude**: explicit, OpenAPI-friendly.

## Non-goals

- **Not a general PII-redaction framework.** This change splits one schema for one route family. A broader policy (e.g. role-based field projection across all endpoints) is out of scope.
- **Not changing admin-view shape.** `UserPublic` is unchanged; admin endpoints continue to include every internal counter they already returned.
- **Not removing `authz_version` from the database or domain.** The field is internal but still needed for cache invalidation; only its HTTP exposure is narrowed.

## Risks / Trade-offs

- **Risk**: a future field gets added to `UserPublic` and forgotten on `UserPublicSelf` (or vice versa). Mitigation: a unit test asserts the symmetric-difference of fields equals the documented set.

## Migration

Single PR. Backwards compatible for legitimate users; clients that pinned on the schema name `UserPublic` for `/me` see a rename.
