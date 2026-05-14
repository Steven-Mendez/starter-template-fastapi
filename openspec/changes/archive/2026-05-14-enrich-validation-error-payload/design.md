## Depends on

- `align-error-class-hierarchy` (so the 422 handler matches the canonical taxonomy).
- `add-stable-problem-types` (the 422 response sets `type` to `urn:problem:validation:failed` from `ProblemType.VALIDATION_FAILED`).

## Conflicts with

Same-file overlap on `src/app_platform/api/error_handlers.py` with `align-error-class-hierarchy`, `add-stable-problem-types`, `declare-error-responses-in-openapi`, `preserve-error-response-headers`, `add-error-reporting-seam`. Agreed merge order for the chain: `align-error-class-hierarchy → add-stable-problem-types → enrich-validation-error-payload → declare-error-responses-in-openapi → preserve-error-response-headers`. The `Violation` shape defined here is consumed by the `ProblemDetails` Pydantic model added in `declare-error-responses-in-openapi`.

## Context

Pydantic's `RequestValidationError.errors()` is a rich, debug-y shape. RFC 9457's `invalid_params` is a thin, client-friendly shape. We translate, and we standardize the field name as `violations` to match this project's terminology (`docs/api.md` already uses "violation" for field-level failures in surrounding sections).

## Decisions

- **Field name `violations: list[Violation]`** on the Problem Details body. Rationale: project-consistent terminology; the canonical RFC 9457 reference is `invalid_params`, but `violations` reads naturally and is what `declare-error-responses-in-openapi` will model in `ProblemDetails`. The catalog in `docs/api.md` cross-references RFC 9457 §3.1.
- **`Violation` shape**: an object with the following fields:
  - `loc: list[str | int]` — the canonical Pydantic location path (`["body", "address", "zip"]` or `["query", "page"]`); preserves the field index unchanged so SDKs can route messages back to the right form field.
  - `type: str` — Pydantic error type (e.g. `value_error`, `missing`, `string_too_short`); stable enough to be a public contract.
  - `msg: str` — human-readable message from Pydantic.
  - `input: object | None` — the offending input value, or `null` if the input is unavailable or sensitive. Always present in dev. **Omitted (key absent) in production** to avoid echoing secrets; the `loc` and `msg` fields stay.
- **Same shape in dev and prod**: production omits only the `input` field; `loc`, `type`, `msg` are identical. Rationale: the production-stripping behaviour today removes too much; clients need the field index regardless of env.
- **Helper lives in `error_handlers.py`**: `pydantic_errors_to_violations(exc: RequestValidationError, *, include_input: bool) -> list[dict]`. Rationale: one entry point keeps the dev/prod branching to a single boolean.

## Risks / Trade-offs

- **Risk**: `type` leaks internal Pydantic validator names. Mitigation: Pydantic codes are stable enough to be a public contract; an alternative project-specific code mapping is more work for marginal benefit.
- **Risk**: `input` echoes secrets in dev. Mitigation: producers MUST treat `input` as a debug aid; the same redaction rules used by `redact-pii-and-tokens-in-logs` apply when this output enters logs.

## Migration

Single PR. Backwards compatible at the protocol level (clients that did not parse 422 bodies are unaffected).
