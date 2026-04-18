## Why

La migración anterior cerró una fase estructural, pero aún mantiene acoplamientos que incumplen DDD/Hexagonal estricto (puertos de aplicación usando modelos HTTP, reglas de negocio duplicadas en adapters de persistencia y falta de guardrails de arquitectura). Con base en la evidencia de terminal (`tests` verdes y `openspec` completo), necesitamos una segunda fase para completar la migración profunda y evitar regresiones de diseño.

## What Changes

- Introducir un modelo de dominio explícito para el contexto Kanban (entidades/value objects) desacoplado de modelos de transporte HTTP.
- Definir mapeadores en la capa de API para convertir request/response DTOs a modelos de aplicación/dominio.
- Mover reglas de movimiento de tarjeta a una única ubicación de dominio reutilizable por todos los adapters.
- Endurecer contratos de repositorio para operar con tipos internos del core y no con esquemas HTTP.
- Aplicar CQRS liviano separando puertos y handlers de comandos y consultas, sin introducir bus de comandos/eventos ni event sourcing.
- Agregar reglas de arquitectura verificables (tests/import boundaries) para forzar la dirección de dependencias.
- **BREAKING** eliminar cualquier expectativa de compatibilidad con estructura híbrida (ya no hay rutas legacy ni contratos acoplados a transporte).

## Capabilities

### New Capabilities
- `domain-kanban-model`: Define entidades y value objects de Kanban para que el core no dependa de modelos de API.
- `application-mapping-boundary`: Define mapeo explícito entre DTOs HTTP y contratos de aplicación.
- `architecture-dependency-rules`: Define validaciones automatizadas de dependencia inward-only entre capas.
- `lightweight-cqrs`: Define separación explícita de command/query handlers y puertos de lectura/escritura sin complejidad de infraestructura CQRS avanzada.

### Modified Capabilities
- `kanban-repository`: El repositorio pasa a contrato de dominio/aplicación puro y elimina acoplamiento con modelos de transporte.
- `domain-specification-pattern`: Las especificaciones de dominio se aplican en una sola fuente de verdad sin duplicación por adapter.
- `api-core`: Los endpoints mantienen contrato HTTP, pero delegan mapping y orquestación a capas internas sin fuga de detalles técnicos.

## Impact

- Código afectado: `src/domain/**`, `src/application/**`, `src/api/**`, `src/infrastructure/persistence/**`, `dependencies.py`, `main.py`.
- Tests afectados: unit de repositorio/use-cases/specifications, integration API, y nuevos tests de reglas de arquitectura.
- Riesgo funcional: bajo sobre contrato HTTP externo, medio sobre estructura interna por cambio de tipos entre capas.
- Beneficio: cumplimiento real DDD/Hexagonal con guardrails para sostener la arquitectura a largo plazo.
