---
description: Apply FastAPI hexagonal architecture rules
---

Use the fastapi-hexagonal-architecture skill.

Review the current FastAPI codebase or the requested feature and apply Hexagonal Architecture:

- keep FastAPI at the API adapter boundary
- keep business rules in the domain layer
- put orchestration in application use cases
- define ports for external dependencies
- implement adapters in infrastructure
- keep Pydantic schemas near the API layer
- keep SQLAlchemy models in infrastructure
- add unit tests for domain and application behavior

User request:

$ARGUMENTS
