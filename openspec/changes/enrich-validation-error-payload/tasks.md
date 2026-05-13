## 1. Build the shape

- [ ] 1.1 Add `pydantic_errors_to_violations(exc: RequestValidationError, *, include_input: bool) -> list[dict]` in `src/app_platform/api/error_handlers.py`.
- [ ] 1.2 For each entry of `exc.errors()`, output `{"loc": list(err["loc"]), "type": err["type"], "msg": err["msg"]}`, adding `"input": err.get("input")` when `include_input` is True.

## 2. Wire into the 422 handler

- [ ] 2.1 Replace the existing dev/prod branching in the 422 handler with a single call to `pydantic_errors_to_violations(exc, include_input=settings.app.environment != "production")`.
- [ ] 2.2 Set the response body's `violations` to the helper's output (always present, even when empty).
- [ ] 2.3 Keep `detail` as a short human-friendly summary (`f"Validation failed: {n} field(s)"`).
- [ ] 2.4 Continue setting `type = ProblemType.VALIDATION_FAILED` (from `add-stable-problem-types`).

## 3. Tests

- [ ] 3.1 Add a test that PATCHes `/me` with an invalid email AND a missing required field; assert `violations` has exactly two entries, each with `loc`, `type`, and `msg`.
- [ ] 3.2 Add the same test under `APP_ENVIRONMENT=production`; assert `violations` has the same two entries with `loc`/`type`/`msg`, and that `input` is absent on each entry.
- [ ] 3.3 Add a test that asserts the body's `type` field equals `urn:problem:validation:failed`.

## 4. Docs

- [ ] 4.1 Document the `Violation` shape and the `violations` field in `docs/api.md` immediately below the Problem Type URN catalog introduced by `add-stable-problem-types`.

## 5. Wrap-up

- [ ] 5.1 Run `make ci` and confirm green.
