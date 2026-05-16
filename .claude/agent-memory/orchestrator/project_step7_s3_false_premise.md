---
name: step7-s3-false-premise
description: ROADMAP step 7's premise is false — the S3 file_storage adapter is a real working boto3 implementation, NOT a NotImplementedError stub
metadata:
  type: project
---

ROADMAP.md line 48 (ETAPA I step 7) says *"Eliminar stub S3 que levanta `NotImplementedError`"* and that the real adapter arrives "~paso 23". **Both are false against the actual codebase** (discovered 2026-05-16 during spec-writer audit):

- `src/features/file_storage/adapters/outbound/s3/adapter.py` is a **fully implemented, contract-tested boto3 adapter** — real `put`/`get`/`delete`/`list`/`signed_url`, presigned URLs, error mapping. Zero `NotImplementedError`.
- It has moto-mocked contract parametrization (`fake`/`local`/`s3`), an 8-test unit suite, the `s3 = ["boto3~=1.34"]` extra, and `boto3`/`moto`/`boto3-stubs` dev deps.
- The canonical `openspec/specs/file-storage/spec.md` has a requirement literally named `S3 adapter is a real boto3 implementation` ("SHALL NOT raise NotImplementedError").
- Only stale in-tree wording (`docs/architecture.md` ~245/251, `src/features/file_storage/__init__.py`, `CLAUDE.md` ~164) falsely calls it a "stub" — that is drift, not dead code.

**Why this matters:** S3 is an AWS adapter; the project is AWS-first; ROADMAP's removal list is "SMTP, Resend, arq, SpiceDB" — S3 is NOT on it. ROADMAP step 24 explicitly wants `aws_s3 adapter real para FileStoragePort`. Deleting the working adapter would be destructive and contradict step 24.

**DECISION (made 2026-05-16 by user — "siempre lo recomendado"): Option A — drift-fix.** Do NOT delete the S3 adapter. Step 7 is implemented as a **drift-fix**: correct the stale "stub/NotImplementedError" wording in `docs/architecture.md` (~245/251), `CLAUDE.md` (~164), `src/features/file_storage/__init__.py`, and fix ROADMAP line 48 (the false "stub … paso 23" text). The real boto3 S3 adapter stays intact (it is what step 24 wants). The spec-writer's earlier `remove-s3-stub` change (authored for deletion) is SUPERSEDED — replaced by a drift-fix change (`fix-s3-stub-drift`). Decision recorded durably in the OpenSpec proposal + a ROADMAP note, not just chat. Related: [[roadmap-workflow]], [[push-blocked-env]], [[default-to-recommended]].

**Adjacent finding (separate honesty defect, out of the 12 steps):** the canonical `openspec/specs/authorization/spec.md` (lines ~169/323/465) describes a nonexistent Kanban feature. Candidate for a dedicated follow-up change; not part of ETAPA I as written.
