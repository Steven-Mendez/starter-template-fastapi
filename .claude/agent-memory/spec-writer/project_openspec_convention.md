---
name: openspec-convention
description: This project uses OpenSpec under openspec/; house style for change proposals and strict-validation delta rules
metadata:
  type: project
---

This repo (starter-template-fastapi) uses **OpenSpec**. Changes live in
`openspec/changes/<kebab-name>/` with `proposal.md`, `tasks.md`, and
`specs/<capability>/spec.md`. Established specs are in `openspec/specs/`.

**Why:** ROADMAP-driven cleanup/feature work is tracked as OpenSpec changes;
the orchestrator runs `openspec validate <name> --strict` after each draft.

**How to apply:**
- `proposal.md` house style (from archived changes): `## Why` (numbered
  concrete failure modes), `## What Changes` (bullets + `**Capabilities —
  Modified**` / `**Capabilities — New**` blocks), `## Impact` (Code /
  Migrations / Tests / Production / Backwards-compat bullets). Add an
  `## Out of scope` section when the change is a deletion adjacent to
  legitimate same-named code.
- Strict validation needs **≥1 delta operation**. A delta `spec.md` uses
  `## ADDED|MODIFIED|REMOVED Requirements`, each `### Requirement: <name>`
  with `MUST/SHALL/SHOULD` text and ≥1 `#### Scenario:` using
  `- **WHEN** / **THEN**` (and optional `- **GIVEN**` / `- **AND**`) bullets.
- For **MODIFIED**, the `### Requirement:` name must match the existing one in
  `openspec/specs/<cap>/spec.md` **exactly**, and the body must restate the
  full SHALL text (carry existing scenarios forward, then add new ones) — the
  archive step replaces the whole requirement block.
- The `authentication` capability owns the production-validator-surface
  requirement `Every documented production refusal has a unit test`
  (`openspec/specs/authentication/spec.md`) — the right MODIFY target for
  settings/validator cleanup changes.
- "oauth" in this repo is mostly legitimate (bearer-token comments,
  `OAuth2PasswordBearer`, `/docs/oauth2-redirect` Swagger path, forward-looking
  `credentials`-table SSO comments). Only the `APP_AUTH_OAUTH_*` Google
  scaffolding was dead config (removed in change `remove-oauth-dead-config`).
