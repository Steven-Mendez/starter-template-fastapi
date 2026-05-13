## Depends on

- `align-error-class-hierarchy` — the URN dispatch uses `isinstance` against the unified `ApplicationError` taxonomy introduced there.

## Conflicts with

Same-file overlap on `src/app_platform/api/error_handlers.py` with `align-error-class-hierarchy`, `enrich-validation-error-payload`, `declare-error-responses-in-openapi`, `preserve-error-response-headers`, `add-error-reporting-seam`. Agreed merge order for the chain: `align-error-class-hierarchy → add-stable-problem-types → enrich-validation-error-payload → declare-error-responses-in-openapi → preserve-error-response-headers`. Land before `declare-error-responses-in-openapi` so the OpenAPI ProblemDetails example carries real URN values.

Same-file overlap on `src/features/authentication/adapters/inbound/http/errors.py` with `preserve-error-response-headers` and `align-error-class-hierarchy`.

Same-file overlap on `src/app_platform/api/schemas.py` with `declare-error-responses-in-openapi` (which adds the `ProblemDetails` model that will quote URN values from this change).

## Context

RFC 9457 says clients should be able to look up a problem `type` in their codebase rather than parse free-form `detail`. The current `about:blank` is the spec's "I have nothing useful to say" value; we have plenty to say.

## Decisions

- **URN scheme `urn:problem:<domain>:<code>`**, written exactly as `urn:problem:<domain>:<code>` where `<domain>` is a lower-kebab capability tag (`auth`, `authz`, `validation`, `generic`) and `<code>` is a lower-kebab error slug. Rationale: stable across versions, project-specific, no dependency on a live URL serving the type definition.
- **Canonical URN catalog** (final values; never renamed, only added):
  - `urn:problem:auth:invalid-credentials`
  - `urn:problem:auth:rate-limited`
  - `urn:problem:auth:token-stale`
  - `urn:problem:auth:token-invalid`
  - `urn:problem:auth:email-not-verified`
  - `urn:problem:authz:permission-denied`
  - `urn:problem:validation:failed`
  - `urn:problem:generic:conflict`
  - `urn:problem:generic:not-found`
- **Enum in `src/app_platform/api/problem_types.py`**: cross-feature, so the home is the platform. Type: `class ProblemType(StrEnum)`.
- **Dispatch by `isinstance` over the `ApplicationError` taxonomy**: rationale: matches how `align-error-class-hierarchy` already maps errors; a single `match`/`isinstance` chain produces both the HTTP status and the URN.
- **Keep `about:blank` for genuinely uncategorized cases**: spec-compliant fallback. Implementation: `ProblemType.ABOUT_BLANK = "about:blank"` sits at the bottom of the chain.

## Risks / Trade-offs

- **Risk**: clients pin on a URN we later rename. Mitigation: URNs are stable strings; never rename, only add.

## Migration

Single PR. Backwards compatible.
