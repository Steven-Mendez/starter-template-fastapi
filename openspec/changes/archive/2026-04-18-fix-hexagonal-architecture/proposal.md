## Why

Actualmente el proyecto presenta desviaciones críticas de las métricas de Arquitectura Limpia/Hexagonal y DDD estipuladas en `SKILL.md`. Contamos con un modelo de dominio anémico (entidades como meros DTO sin comportamiento), un repositorio de formato Dios (CRUD para cada tabla saltándose los Aggregates), y carecemos de un patrón `Unit of Work` en nuestros manejadores de comandos (comandos de manipulación dual, como mover una tarjeta, pueden fallar y dejar estados inconsistentes sin transacciones atómicas). Arreglar esto es imperativo para mantener una base de código estructurada, probada y resistente frente al crecimiento, limitando la deuda técnica a tiempo.

## What Changes

- **Refactorización de Entidades (Rich Entities)**: Se moverá la lógica procedimental distribuida (como el ordenamiento o validaciones para mover tarjetas) directamente a métodos dentro del Aggregate Root (`Board`) o entidades core (`Card` / `Column`).
- **Implementación del Unit of Work**: Se introducirá una abstracción `UnitOfWork` que los Command Handlers utilizarán explícitamente para demarcar el contexto transaccional ACID de principio a fin.
- **Rediseño del Repositorio**: Se acotará el repositorio `KanbanRepository` para que brinde un servicio atado únicamente a la lectura o persistencia del Aggregate `Board`, erradicando operaciones específicas aisladas directas como `update_card` o `apply_card_sequence`.
- **Limpieza de Artifacts Residuales**: Eliminación o adecuación de `KanbanUseCases` inactivos en el Application Layer que no se están utilizando (la API recurre directamente a CQRS command/query handlers, y mantener dos capas similares ociosas induce a la confusión).

## Capabilities

### New Capabilities

- `transactional-unit-of-work`: Establecimiento de un contrato para el Unit of Work en el application shared layer (`src/application/shared/unit_of_work.py`) y sus implementaciones concretas en las capas de persistencia y en memoria.

### Modified Capabilities

- `domain-kanban-model`: Evoluciona de @dataclasses anémicas a Rich Entities con comportamiento interno y encapsulamiento.
- `kanban-repository`: Cambia de un God Repository CRUD basado en tablas a un Repositorio por Aggregate Root (el Board).
- `lightweight-cqrs`: Los Command Handlers se actualizarán para hacer uso exclusivo de `UnitOfWork` y de interacciones a nivel de Aggregate en lugar de múltiples lecturas/escrituras aisladas al repositorio.

## Impact

Este rediseño afectará fundamentalmente a `src/domain/kanban/` (modelos, servicios y repositorios), `src/application/commands/` (Command Handlers) y las implementaciones de repositorios correspondientes en `src/infrastructure/persistence/`. Los endpoints del API Router no deberían variar sus firmas públicas ni contratos HTTP.
