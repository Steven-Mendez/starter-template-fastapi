## Depends on

- `align-error-class-hierarchy` (the `ProblemDetails` model documents the unified error taxonomy).
- `add-stable-problem-types` (`ProblemDetails.type` is documented as a URN drawn from `ProblemType`).
- `enrich-validation-error-payload` (the `ProblemDetails.violations` field uses the `Violation` shape defined there).

## Conflicts with

Same-file overlap on `src/app_platform/api/error_handlers.py` with `align-error-class-hierarchy`, `add-stable-problem-types`, `enrich-validation-error-payload`, `preserve-error-response-headers`, `add-error-reporting-seam`. Agreed merge order for the chain: `align-error-class-hierarchy → add-stable-problem-types → enrich-validation-error-payload → declare-error-responses-in-openapi → preserve-error-response-headers`.

Same-file overlap on `src/app_platform/api/schemas.py` with `add-stable-problem-types` (URN values quoted in the model docstring).

## Context

OpenAPI completeness matters for downstream SDK generation. Each missing piece — error responses, stable operation IDs, the `ProblemDetails` schema — costs SDK consumers concrete time.

## Decisions

- **One reusable `PROBLEM_RESPONSES` dict** in `src/app_platform/api/responses.py`: define it once; spread per-route. Per-route subsets are explicit.
- **`operationId` convention `{router_name}_{handler_name}` (snake_case)**. Rationale: the user explicitly chose this form; it survives function renames less well than a hand-curated `feature.verb_resource`, but it is mechanically derivable from the existing router + handler names without bikeshedding. Implementation: a `generate_unique_id_function = lambda route: f"{route.tags[0] if route.tags else 'root'}_{route.name}"` installed on every `APIRouter`, where `route.name` is the snake_case handler function name and `route.tags[0]` is the feature tag (already set on every existing router).
  - Examples produced by this rule: `auth_login`, `auth_logout`, `users_get_me`, `users_patch_me`, `users_delete_me`, `admin_list_users`, `health_live`.
- **`ProblemDetails` Pydantic model in `src/app_platform/api/schemas.py`** with fields `type: str`, `title: str`, `status: int`, `detail: str | None = None`, `instance: str | None = None`, `violations: list[Violation] | None = None`. `type` is documented as the URN string defined by `ProblemType`.
- **`Violation` Pydantic model in the same module** with fields `loc: list[str | int]`, `type: str`, `msg: str`, `input: object | None = None`. Mirrors the runtime shape produced by `enrich-validation-error-payload`.

## Risks / Trade-offs

- **Risk**: route signatures get noisier with the new kwarg. Mitigation: a `feature_responses` constant per feature keeps the per-route line short (one `responses=feature_responses` token).
- **Risk**: the snake_case generator collides for routes with identical handler names in the same router. Mitigation: handler names in this codebase are already unique within a router; the test in tasks 4.x guards against future collisions.

## Migration

Single PR. Backwards compatible.
