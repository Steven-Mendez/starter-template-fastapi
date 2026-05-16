# Tasks — remove-oauth-dead-config

## 1. Remove the env-var contract

- [ ] In `.env.example`, delete lines for `APP_AUTH_OAUTH_ENABLED`,
      `APP_AUTH_OAUTH_GOOGLE_CLIENT_ID`, `APP_AUTH_OAUTH_GOOGLE_CLIENT_SECRET`,
      `APP_AUTH_OAUTH_GOOGLE_REDIRECT_URI` (currently lines 80–83), plus any
      comment/header line dedicated solely to OAuth in that block. Leave the
      surrounding `APP_AUTH_RETURN_INTERNAL_TOKENS` and `APP_AUTH_REDIS_URL`
      entries and their comments untouched.

## 2. Remove the settings fields

- [ ] In `src/app_platform/config/settings.py`, delete the
      `# TODO: OAuth login is not implemented yet ...` comment and the four
      `auth_oauth_*` fields (currently lines 148–153). Keep
      `auth_super_admin_role` above and `auth_return_internal_tokens` (with its
      comment) below.
- [ ] In `src/features/authentication/composition/settings.py`, delete the
      four `oauth_*` fields from the `AuthenticationSettings` dataclass
      (currently lines 45–48) and the four `oauth_*=app.auth_oauth_*`
      assignments in `from_app_settings` (currently lines 94–97).

## 3. Remove the dead container code

- [ ] In `src/features/authentication/composition/container.py`, delete the
      `_warn_unused_oauth_settings(...)` call site inside `build_auth_container`
      (currently line 190) and the entire `_warn_unused_oauth_settings`
      function definition (currently lines 372–385). Verify no other reference
      to it remains (grep `_warn_unused_oauth_settings`).

## 4. Delete the now-orphaned test

- [ ] In
      `src/features/authentication/tests/integration/test_auth_container_rate_limiter.py`,
      delete `test_build_auth_container_warns_for_unimplemented_oauth_settings`
      (currently lines 66–85). Remove any import (`logging`, `caplog`-only
      helpers) that becomes unused solely because of this deletion; leave
      imports still used by sibling tests.

## 5. Remove the documentation references

- [ ] In `docs/operations.md`, delete the `### OAuth Preparation` section
      (currently lines 366–377), including its bullet list and trailing prose.
- [ ] In `docs/operations.md`, delete the four `APP_AUTH_OAUTH_*` rows from the
      env-var reference table (currently lines 806–809). Leave the table header
      and all non-OAuth rows intact.

## 6. Audit confirmation (no code change expected)

- [ ] Confirm `AuthenticationSettings.validate_production` and
      `AppSettings.validate_production` contain **no** OAuth entry (grep
      `oauth` in both — expected: zero matches after steps 2–3). If an OAuth
      validation entry is found, STOP and flag it: the proposal asserts none
      exists.

## 7. Verify the repo is clean and green

- [ ] Repo-wide grep: `APP_AUTH_OAUTH`, `auth_oauth`, `oauth_enabled`,
      `oauth_google`, `_warn_unused_oauth` return only the OUT-OF-SCOPE sites
      enumerated in `proposal.md` (bearer-token comments,
      `OAuth2PasswordBearer`, `/docs/oauth2-redirect`, forward-looking
      `credentials`-table / SSO comments, and the ROADMAP line itself).
- [ ] `make quality` is green (lint + arch + typecheck — removing the unused
      `AppSettings` fields and projection fields must not break import-linter
      or mypy).
- [ ] `make test` is green (unit + e2e). The deleted integration test must no
      longer be collected; no remaining test references the removed surface.
