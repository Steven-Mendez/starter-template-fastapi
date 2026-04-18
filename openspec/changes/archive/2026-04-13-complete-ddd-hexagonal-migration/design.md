## Context

El repositorio reporta todos los tests en verde y OpenSpec marca la migración previa como completa, pero ese estado refleja estabilidad funcional, no cumplimiento arquitectónico total. Persisten decisiones transicionales: contratos de aplicación reutilizan DTOs HTTP, parte de reglas de negocio sigue en adapters de persistencia y no hay una política automatizada suficiente que bloquee dependencias inválidas entre capas.

## Goals / Non-Goals

**Goals:**
- Separar completamente modelos de dominio/aplicación de modelos de transporte HTTP.
- Consolidar reglas de negocio de movimiento en dominio para evitar duplicación por adapter.
- Convertir el puerto de repositorio en contrato interno puro (sin tipos API).
- Introducir CQRS liviano con separación command/query en aplicación para mejorar claridad y testabilidad.
- Definir validaciones automáticas de arquitectura para mantener la regla de dependencia inward-only.
- Mantener estable el contrato HTTP público existente.

**Non-Goals:**
- Rediseñar endpoints, payloads o semántica externa de la API.
- Introducir CQRS avanzado (bus distribuido, proyecciones asíncronas o event sourcing).
- Cambiar stack técnico principal (FastAPI, SQLModel, Alembic).
- Reescribir toda la suite de tests desde cero.

## Decisions

1. **Modelo de dominio explícito para Kanban**
   - Decision: introducir tipos de dominio para Board/Column/Card y usar esos tipos en puertos internos.
   - Rationale: evita que el core dependa de Pydantic/HTTP concerns.
   - Alternative: seguir con DTOs de API en puertos; descartado por violar separación hexagonal.

2. **Boundary mapper en API adapter**
   - Decision: `src/api` mapea request DTO -> input de aplicación y output de aplicación -> response DTO.
   - Rationale: aísla transporte en el borde.
   - Alternative: mapear en repositorios o use cases; descartado por mezclar responsabilidades.

3. **Reglas de movimiento en dominio compartido**
   - Decision: mantener especificaciones de dominio como única implementación de reglas y reusar desde aplicación/adapters sin duplicación de lógica.
   - Rationale: consistencia funcional entre adapters y menor costo de evolución.
   - Alternative: reglas específicas por adapter; descartado por divergencia.

4. **Guardrails de arquitectura**
   - Decision: añadir tests de boundary (imports prohibidos/permitidos) para codificar la Dependency Rule.
   - Rationale: evita recaídas arquitectónicas en cambios futuros.
   - Alternative: solo convención documental; descartado por fragilidad.

5. **CQRS liviano en capa de aplicación**
   - Decision: separar explícitamente handlers/puertos de comandos (write) y consultas (read), manteniendo mismo modelo de persistencia y mismas transacciones.
   - Rationale: clarifica responsabilidades sin incorporar complejidad operativa de CQRS full.
   - Alternative: mantener use cases mixtos por operación; descartado por mezclar lectura/escritura y dificultar evolución.

## Risks / Trade-offs

- **[Risk] Ruptura interna por cambio de tipos en puertos** -> **Mitigation:** migrar por slices con adapters de mapeo y tests de contrato en cada paso.
- **[Risk] Sobrecosto de mapeo DTO<->dominio** -> **Mitigation:** crear mappers simples y centralizados en `src/api`.
- **[Risk] Incremento de complejidad en corto plazo** -> **Mitigation:** limitar scope al bounded context Kanban y mantener contrato externo estable.
- **[Risk] Sobrediseño CQRS para tamaño actual** -> **Mitigation:** aplicar separación solo a nivel de interfaces/handlers, sin buses ni read models separados.
- **[Risk] Falsos positivos en tests de arquitectura** -> **Mitigation:** definir reglas precisas por módulo y ajustar únicamente imports arquitectónicamente válidos.

## Migration Plan

1. Definir modelos de dominio Kanban y adaptar puertos de aplicación a esos tipos.
2. Introducir mappers en API y ajustar use cases a contratos internos.
3. Actualizar adapters de persistencia para mapear entre modelos de dominio y tablas SQLModel.
4. Consolidar especificaciones de dominio como fuente única de reglas de movimiento.
5. Introducir puertos y handlers CQRS livianos (commands/queries) y adaptar API a esta separación.
6. Añadir tests de arquitectura (dependencias por capa) y endurecer suite existente.
7. Ejecutar validación completa (`ruff`, `mypy`, `pytest`, OpenSpec apply status).

## Open Questions

- ¿Los tipos de command/query se modelarán como DTOs dedicados o como aliases sobre contratos de dominio inicialmente?
- ¿Incorporamos una regla automatizada adicional (beyond tests) para bloquear imports inválidos en CI?
- ¿Qué naming final tendrá el capability histórico `kanban-*` una vez converja el bounded context con naming neutral?
