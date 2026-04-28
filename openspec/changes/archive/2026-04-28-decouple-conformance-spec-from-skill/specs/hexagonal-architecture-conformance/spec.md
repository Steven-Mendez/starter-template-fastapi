## MODIFIED Requirements

### Requirement: Automated Conformance Suite is the Source of Truth
The system MUST treat the architecture conformance test suite as the single source of truth for hexagonal-architecture compliance with this capability. The requirements declared in this specification MUST be encoded as machine-verifiable tests under `tests/architecture/`, and a passing suite MUST imply conformance with this capability.

#### Scenario: Conformance suite gate present
- **WHEN** the project's automated checks (`make check`, `pre-commit`, or CI) run
- **THEN** the suite under `tests/architecture/` executes and a non-zero exit code blocks the build

### Requirement: Anti-Pattern Guards Applied to Application Classes
The conformance suite MUST flag application-layer anti-patterns that contradict the use-case-cohesion capability. At minimum the suite MUST detect (a) generic service objects that aggregate multiple unrelated business intents on a single class, and (b) anemic pass-through use cases that delegate to a single repository method without invoking any domain object.

#### Scenario: Mega service detected
- **WHEN** a class under `src/application/` declares more than one public method that is part of an inbound port and is not a use case
- **THEN** the conformance suite fails citing the `use-case-cohesion` capability

#### Scenario: Anemic pass-through use case detected
- **WHEN** a class ending in `UseCase` under `src/application/use_cases/` has an `execute` method whose body delegates to a single repository method without invoking any domain object
- **THEN** the conformance suite emits a warning entry naming the file (the warning category SHALL be reviewable in CI logs)

## REMOVED Requirements

### Requirement: Conformance Diagnostics Reference the Skill
**Reason**: The `fastapi-hexagonal-architecture` skill is descriptive support material for the AI agent, not a normative artifact. Diagnostic strings should reference the spec capability that defines the rule, not an external skill that may be replaced or removed without changing system behavior.
**Migration**: Replaced by `Conformance Diagnostics Reference the Spec Capability`. The mandated substring becomes `hexagonal-architecture-conformance:` instead of `fastapi-hexagonal-architecture:`. The architecture suite has already been updated to emit the new prefix.

## ADDED Requirements

### Requirement: Conformance Diagnostics Reference the Spec Capability
Each architecture test failure MUST surface a diagnostic that names the spec capability whose requirement is being enforced so that developers and agents can locate the normative rule directly in `openspec/specs/<capability>/spec.md` without consulting external material.

#### Scenario: Failure message cites the spec capability
- **WHEN** the conformance suite fails any assertion that enforces this capability
- **THEN** the assertion message contains the substring `hexagonal-architecture-conformance:` followed by a short human-readable description of the violated rule

#### Scenario: Failure message cites the relevant capability when not this one
- **WHEN** the conformance suite fails an assertion that enforces a different hex-related capability (e.g., `use-case-cohesion`, `adapter-topology-conventions`, `error-boundary-and-translation`)
- **THEN** the assertion message contains the substring `<capability-name>:` matching the kebab-case capability id under `openspec/specs/`
