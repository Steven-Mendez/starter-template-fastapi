## MODIFIED Requirements

### Requirement: Governance mode SHALL be zero-exception in CI
The system SHALL enforce architecture and spec-governance checks in CI without skip paths, including catalog-level OpenSpec structural validation.

#### Scenario: OpenSpec catalog structure violations exist
- **WHEN** CI runs `openspec validate --all`
- **THEN** the pipeline SHALL fail if any spec lacks canonical `## Purpose` and `## Requirements` sections

#### Scenario: Placeholder spec purpose text is present
- **WHEN** a main spec uses placeholder intent text (for example `TBD`)
- **THEN** governance checks SHALL fail until concrete purpose text is provided
