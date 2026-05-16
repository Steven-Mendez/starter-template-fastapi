---
name: s3-stub-drift-false-premise
description: ROADMAP ETAPA I step 7 was NOT a stub deletion — S3 adapter is real boto3, retained (Option A). Step 7 is a wording-only drift fix.
metadata:
  type: project
---

ROADMAP ETAPA I step 7 ("Eliminar stub S3 que levanta `NotImplementedError`")
rested on a **false premise**: there is no S3 stub.
`src/features/file_storage/adapters/outbound/s3/adapter.py` is a real
`boto3` `S3FileStorageAdapter` (put/get/delete/list/signed_url, moto-contract
tested, 0 `NotImplementedError`). The owner's recorded decision (2026-05-16,
in `fix-s3-stub-drift/proposal.md`) is **Option A — drift-fix, not deletion**:
adapter RETAINED unchanged; step 7 only corrects stale "stub" prose.

**Why:** S3 is the AWS-native backend ROADMAP step 24 wants kept; it is NOT
on the remove list (SMTP/Resend/arq/SpiceDB). Deleting it would be
destructive and contradict the AWS-first norte.

**How to apply when reviewing fix-s3-stub-drift or its archive/step-24
successor:**
- The change is WORDING-ONLY. `git diff -- s3/adapter.py tests/ pyproject.toml
  uv.lock` MUST be empty; any settings/`StorageBackend` Literal/validator/
  migration edit = Critical.
- Exactly 5 wording sites: `file_storage/__init__.py` docstring (drop "stub",
  keep accurate "ships as scaffolding ready to be wired in" — that describes
  the *feature being unwired*, NOT the adapter), `docs/architecture.md` rows
  ~36 (feature table) / ~245 (Design-Decisions — REWRITE the row to the
  provider-agnostic `AWS_ENDPOINT_URL_S3` decision, do NOT delete) / ~251
  (Tradeoffs — reframe as operational prereq, do NOT delete), `ROADMAP.md`
  line 48 ONLY (+ `[x]`).
- `README.md:53` and `CLAUDE.md:164` carry the same false "stub" wording but
  are DEFERRED to ROADMAP steps 9/10 (wholesale rewrites). NOT in diff =
  correct. Steps 9/10 must land "real boto3 adapter", never "stub".
- `ROADMAP.md` line ~121 ("Eliminar el 'stub eliminado' del paso 7") is
  step-24's sub-bullet — deliberately left untouched here; step 24 owns it.
- Spec delta: single `## MODIFIED` on project-layout "Documentation reflects
  the new layout" (header byte-matches canonical line 93). Carve-out in para
  2 + scenario "Docs do not instruct recovering the removed scaffold" final
  AND-bullet narrow from `S3 "ships as scaffolding" stub note` →
  `feature's "ships as scaffolding ready to be wired in" note`. New SHALL
  para + new scenario "No documentation describes the real S3 adapter as a
  stub" added. All 4 prior scenarios + api.md clause carried verbatim.
  Archive WITHOUT --skip-specs.
- Proof gate: `make quality` (22 contracts, mypy 479 files) + `make test`
  (763 pass, 65 deselected) + `uv run pytest src/features/file_storage/`
  (38 pass) all green confirms zero behavioural change.
