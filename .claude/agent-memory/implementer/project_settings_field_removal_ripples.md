---
name: project-settings-field-removal-ripples
description: Removing an APP_* field from AppSettings during an ETAPA I adapter removal also breaks platform projections/observability that read it; the spec audit can miss these
metadata:
  type: project
---

When an ETAPA I adapter-removal change deletes `APP_*` fields from
`AppSettings` (e.g. `jobs_redis_url`, `jobs_queue_name` in
`remove-arq-adapter`), the spec's stated edit list (main.py, the feature
container/settings) is usually NOT exhaustive. Real out-of-feature
consumers also read those fields and break the build/tests:

- `src/app_platform/config/sub_settings.py` — `ObservabilitySettings`
  projects per-feature fields (it had `jobs_redis_url`) and its
  `from_app_settings` assigns `app.jobs_redis_url`.
- `src/app_platform/observability/tracing.py` — gated the Redis
  instrumentor on `auth_redis_url or jobs_redis_url`.
- `src/cli/create_super_admin.py` — a second composition root that calls
  `JobsSettings.from_app_settings(backend=, redis_url=, queue_name=)`
  exactly like `main.py` (the spec only named main.py).
- Tests under `app_platform/tests/unit/observability/` construct
  `AppSettings(**{...})` / `ObservabilitySettings(...)` with the removed
  kwarg and have a dedicated `test_..._when_<field>_set`.

**Why:** discovered implementing `remove-arq-adapter` — `make test`
went 69-failed/171-errors from a single `AttributeError:
'AppSettings' object has no attribute 'jobs_redis_url'` raised inside
the `_validate_auth_settings` model_validator at conftest fixture
setup, which cascaded across the whole suite.

**How to apply:** before declaring a settings-field removal done, run
`grep -rn '<field_name>' src/ --include=*.py` (NOT just the feature
dir). Fix every real consumer minimally and flag it (it is
coherence-required, not scope creep — the spec mandates `make test`
green). Also: `_VALID_PROD_ENV` removal of a backend key makes that
backend's production refusal *always-present* alongside the email one
from step 4 — update the shared `_assert_only_*` helper to expect BOTH
bullets, not one. See [[project-settings-literal-validation-order]] and
[[project-roadmap-etapa-i]].
