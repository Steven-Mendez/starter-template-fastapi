---
name: etapa1-adapter-removal
description: ROADMAP ETAPA I removes non-AWS production adapters one step per OpenSpec change; the production-validator must stay an honest refusal, not relax
metadata:
  type: project
---

ROADMAP ETAPA I (steps 3–7) removes non-AWS production-shaped adapters one at
a time, one OpenSpec change each: 3=SMTP (archived
`2026-05-16-remove-smtp-adapter`), 4=Resend (`remove-resend-adapter`),
5=arq, 6=SpiceDB stub, 7=S3 stub. Dev-only adapters (`console`, `in_process`,
`local`, `in_memory`) stay. Real AWS adapters arrive much later (SES at
step 25). Ports are kept (testability, not portability).

**Why:** AWS-first starter; "una sola opción opinada > tres opciones a
medias"; the ROADMAP norte is an honest repo mid-cleanup.

**How to apply (key recurring design call):** when an adapter removal makes a
backend `Literal` collapse to a single dev-only value, the production
validator that refuses that dev value MUST keep refusing it — do NOT relax it
so production boots. Rationale: the refusal exists so production never
silently uses a dev sink (e.g. `console` email black-holes mail). Removing
the last production backend makes production-with-that-feature intentionally
not bootable until the AWS adapter lands; that is the honest state, not a
regression. The ONLY forced code change is rewording the validator message to
stop naming the removed backend. This recurs for email (step 4) and will
recur for any future single-value collapse.

**Test ripple to always flag:** `src/app_platform/tests/test_settings.py`
has a shared `_VALID_PROD_ENV` baseline that prior steps repoint to whatever
backend is still production-valid. When no production-valid value remains,
repoint it to the dev value and isolate the now-always-present refusal in
every test that reuses the baseline to assert a *different* refusal.

Do NOT pre-empt later doc-rewrite steps: step 9=README, 10=CLAUDE,
11=`docs/operations.md` "production refuses to start if…" narrative. Adapter-
removal changes touch only the removed backend's lines + minimal honest
restatement. See [[openspec-convention]] for the MODIFY targets (email,
project-layout, quality-automation, authentication validator-surface).
