## Why

The previous hardening pass removed major hexagonal leaks, but a focused audit still found residual gaps:

- Column deletion in command handlers depends on a missing aggregate method and can leave non-contiguous column positions.
- Domain aggregate logic still invokes a child entity private method, weakening encapsulation.
- Architecture tests can still miss some boundary bypasses (dependency graph and import-style variants).
- The OpenSpec catalog still has invalid legacy specs and placeholder Purpose text, so `openspec validate --all` is not fully green.

## What Changes

- Define stricter aggregate invariants for column removal/reindexing and private-method encapsulation.
- Strengthen architecture dependency governance to include runtime dependency graph checks and robust import parsing.
- Extend hexagonal inbound-boundary rules to block direct route dependency on container providers.
- Add catalog governance requirements so all specs keep valid structure and no placeholder Purpose text.

## Capabilities

### Modified Capabilities
- `domain-kanban-model`
- `repository-aggregate-compliance`
- `architecture-dependency-rules`
- `hexagonal-layer-boundaries`
- `architecture-import-governance`

## Impact

- Affected areas: domain aggregate behavior, command handler orchestration, architecture tests, and OpenSpec specification hygiene.
- Goal: remove residual hexagonal boundary drift and bring full-spec validation back to a clean baseline.
