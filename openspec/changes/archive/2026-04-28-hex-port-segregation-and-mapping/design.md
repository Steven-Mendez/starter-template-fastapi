## Context

Hexagonal architecture depends on well-defined ports with single responsibilities. The current structure has query-related lookups in command ports and infrastructure mappers tied to application DTOs, which creates cross-layer coupling. A refined port and mapping model is required to keep the business core stable as read/write concerns evolve.

## Goals / Non-Goals

**Goals:**
- Enforce explicit responsibility boundaries among command, query, and lookup ports.
- Ensure infrastructure mapping modules depend only on domain and persistence models, not application DTO contracts.
- Provide a read-model contract strategy that keeps use cases and HTTP serializers decoupled.
- Preserve functional behavior while improving architectural correctness.

**Non-Goals:**
- Full event-sourced CQRS migration.
- Reworking every endpoint payload format.
- Introducing a new ORM or persistence engine.

## Decisions

1. Split command and query interfaces into dedicated ports with no cross-concern methods.
   - Rationale: each port becomes cohesive and implementation behavior is predictable.
   - Alternative: keep shared methods in command ports for convenience. Rejected due to leakage and unclear ownership.

2. Create an optional lookup port for command preconditions that need lightweight reads.
   - Rationale: avoids bloating command repository while enabling minimal read dependencies in command flow.
   - Alternative: route all lookups through query port. Rejected when lookup semantics differ from projection semantics.

3. Move application DTO shaping out of persistence mappers into application or inbound adapter mapping layer.
   - Rationale: persistence adapters should not know transport-facing contracts.
   - Alternative: keep DTO generation in infrastructure for speed. Rejected due to coupling cost over time.

4. Define adapter conformance tests per port to ensure segregation is maintained.
   - Rationale: catches accidental boundary erosion in future additions.

## Risks / Trade-offs

- [Risk] Refactor introduces temporary duplication in mapping logic → Mitigation: create shared pure mapping helpers and remove duplicates incrementally.
- [Risk] Use cases may require signature changes across many files → Mitigation: phase migration with compatibility adapters.
- [Risk] Over-segmentation could add complexity for small teams → Mitigation: keep only three port families (command/query/lookup) and avoid extra abstraction layers.
