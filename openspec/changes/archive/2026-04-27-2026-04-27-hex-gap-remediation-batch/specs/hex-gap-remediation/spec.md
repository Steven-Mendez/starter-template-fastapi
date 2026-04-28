# Spec: Hex Gap Remediation Batch

**Capability**: hex-gap-remediation
**Change**: 2026-04-27-hex-gap-remediation-batch

---

## ADDED Requirements

### Requirement: HGR-01 — Active remediation batch is tracked as an in-progress OpenSpec change

**Priority**: High

The system MUST maintain an active OpenSpec change artifact while multi-capability architectural remediation is in progress.

**Acceptance Criteria**:
1. `openspec/changes/2026-04-27-hex-gap-remediation-batch/proposal.md` exists.
2. `openspec/changes/2026-04-27-hex-gap-remediation-batch/tasks.md` exists.
3. `openspec/changes/2026-04-27-hex-gap-remediation-batch/specs/hex-gap-remediation/spec.md` exists.

#### Scenario: OpenSpec dashboard shows an active change

- Given: the repository OpenSpec tree
- When: `openspec view` is executed
- Then: Active Changes is greater than zero

### Requirement: HGR-02 — Remediation capabilities are implemented with non-e2e suite green

**Priority**: High

The remediation batch MUST preserve runtime behavior while improving architectural boundaries and guardrails.

**Acceptance Criteria**:
1. Non-e2e tests pass (`pytest -m "not e2e"`).
2. The following capabilities have implementation + tests in this batch:
   - transaction boundaries
   - domain command validation for patch
   - query card lookup
   - API error contract
   - health readiness contract
   - write API-key auth
   - test/CI guardrails
   - dependency readiness
   - application error resilience
   - aggregate encapsulation
   - query adapter isolation

#### Scenario: Batch verification succeeds

- Given: the remediation changes are present
- When: `uv run pytest -m "not e2e"` is executed
- Then: all selected tests pass
