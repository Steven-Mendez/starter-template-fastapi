# composition-root-wiring Specification

## Purpose

Centralize adapter selection and lifecycle ownership in a composition root so repository ports and domain code stay free of runtime wiring concerns.

## Requirements

### Requirement: Runtime adapter selection SHALL be centralized

The system SHALL centralize settings-driven adapter selection in a composition root module and SHALL keep this logic out of repository port modules.

#### Scenario: Backend is selected from settings in one place

- **WHEN** application settings specify `memory`, `sqlite`, or `postgresql` backend
- **THEN** composition root wiring SHALL instantiate the matching adapter implementation

### Requirement: Lifecycle management SHALL be owned by composition root

The system SHALL own startup/shutdown lifecycle hooks for stateful adapters in composition root wiring.

#### Scenario: Repository resources are closed on shutdown

- **WHEN** the application lifecycle ends
- **THEN** composition root shutdown logic SHALL call adapter close/disposal hooks exactly once
