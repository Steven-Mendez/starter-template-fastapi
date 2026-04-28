# Proposal: Hexagonal Gap Remediation Batch

**Change ID**: `2026-04-27-hex-gap-remediation-batch`
**Priority**: High
**Status**: Completed

---

## Problem Statement

The codebase had multiple architectural gaps identified by concurrent audits (transaction ownership ambiguity, API error-contract drift risk, health contract hardcoding, patch validation at adapter edge, missing write-edge auth, and CI/test guardrail gaps). Work has started across these concerns, but OpenSpec had no active change artifact tracking this implementation batch.

## Scope

In scope:
- Track and complete the active remediation batch that spans:
  - transaction boundaries
  - domain command validation for patch paths
  - direct query card lookup
  - API error contract hardening
  - health readiness contract decoupling
  - write API-key edge protection
  - CI guardrails and integration composition fidelity
  - dependency readiness 503 handling
  - application error resilience fallback
  - aggregate encapsulation (board column mutation intent)
  - query adapter isolation

Out of scope:
- Full persistence redesign and optimistic locking rollout
- Complete value-object migration for IDs/titles/positions

## Why now

These are high-leverage architecture fixes that reduce coupling and failure ambiguity while preserving existing API behavior. They also improve regression resistance through targeted tests and CI gates.

## Acceptance targets

1. All non-e2e tests pass after the batch.
2. OpenSpec has an active change in progress documenting this batch.
3. Batch capabilities are documented in root specs under `openspec/specs/*`.
