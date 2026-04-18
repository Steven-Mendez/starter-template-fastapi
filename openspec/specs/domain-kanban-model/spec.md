# domain-kanban-model Specification

## Purpose

Model Kanban boards, columns, and cards as explicit domain constructs with invariants expressed in domain code, independent of web frameworks and persistence mapping types.

## Requirements

### Requirement: Domain model SHALL define Kanban entities independently of HTTP schemas

The system SHALL define explicit domain entities/value objects for board, column, and card behavior without importing FastAPI or API schema modules.

#### Scenario: Domain entity imports stay infrastructure-free

- **WHEN** domain model modules are inspected
- **THEN** they SHALL NOT import FastAPI, Pydantic API schemas, SQLModel table classes, or application settings

### Requirement: Domain model SHALL represent business invariants directly

The system SHALL represent card movement invariants and ordering semantics through domain-level types and methods/specifications.

#### Scenario: Card move invariants are evaluated in domain

- **WHEN** a move request is processed
- **THEN** validation for target existence and same-board constraints SHALL be evaluated through domain model/specifications
