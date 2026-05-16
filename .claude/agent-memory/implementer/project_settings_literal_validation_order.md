---
name: project-settings-literal-validation-order
description: Narrowing an AppSettings Literal field changes which layer rejects an out-of-range env value (pydantic field validation, not the EmailSettings/sub-settings guard)
metadata:
  type: project
---

When an `AppSettings` field is a `Literal[...]` (e.g. `email_backend:
Literal["console"]`), pydantic-settings rejects an out-of-range env
value at **field validation**, BEFORE the `@model_validator` runs. The
error message names the **field** (`email_backend`) and says
`Input should be 'console'` — it does NOT contain the `APP_*` env-var
name, and the per-feature `from_app_settings` guard's `ValueError`
(which does name `APP_EMAIL_BACKEND`) never executes for that path.

**Why:** discovered implementing `remove-resend-adapter` — tests that
did `pytest.raises(ValidationError, match="APP_EMAIL_BACKEND")` after
narrowing `email_backend` to a single-value Literal failed, because the
literal_error message names the field, not the env var.

**How to apply:** when narrowing/adding a Literal on `AppSettings`,
assert on the field name + allowed value (`"email_backend" in msg`,
`"'console'" in msg`), not the `APP_*` env var, for the *AppSettings*
construction path. The `APP_*`-named message only appears when calling
the sub-settings `from_app_settings(backend=...)` classmethod directly
(string param, no Literal coercion). Ruff PT011 also forces a `match=`
on `pytest.raises(ValueError)` (but not on `ValidationError`).
