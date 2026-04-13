## Context

Card movement rules (for example, cross-board move rejection) are implemented directly inside repository methods. This couples rule declarations to persistence details and makes isolated rule testing less direct.

## Goals / Non-Goals

**Goals:**
- Introduce a small Specification Pattern abstraction with logical composition.
- Represent card movement business rules as explicit specification objects.
- Use the same rule objects from both in-memory and SQLite repository paths.

**Non-Goals:**
- Replace all domain validation in one pass.
- Change external HTTP/API semantics.
- Add third-party rule engines.

## Decisions

- Add a generic `Specification[T]` abstraction with `is_satisfied_by` and composition (`and`, `or`, `not`).
- Define a movement candidate model carrying only data needed for rule evaluation.
- Implement card move rule specifications (target column exists, same-board movement).
- Repositories will build candidates and evaluate composed specs before mutating state.

## Risks / Trade-offs

- [More abstraction] -> Keep API minimal and focused on real rule reuse.
- [Rule duplication between data fetch and rule evaluation] -> Limit specifications to business predicates; persistence lookups remain in repositories.
- [Over-engineering concern] -> Start with card movement rules only and expand when new reuse appears.
