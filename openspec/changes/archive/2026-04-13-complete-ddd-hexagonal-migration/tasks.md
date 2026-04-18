## 1. Domain Core Separation

- [x] 1.1 Introducir entidades/value objects de Kanban en `src/domain/kanban` sin dependencias de API o infraestructura.
- [x] 1.2 Ajustar errores y utilidades de resultado para uso canónico desde `src/domain/shared`.
- [x] 1.3 Consolidar especificaciones de movimiento como única implementación de reglas de dominio.

## 2. Application Contract Refactor

- [x] 2.1 Redefinir puertos de aplicación para usar contratos internos (no DTOs HTTP).
- [x] 2.2 Actualizar use cases para orquestar validaciones/reglas con tipos internos.
- [x] 2.3 Agregar/ajustar tests unitarios de use cases sobre contratos internos.

## 3. API Boundary Mapping

- [x] 3.1 Introducir mappers de boundary en `src/api` para request DTO -> input de aplicación.
- [x] 3.2 Introducir mappers de boundary para output de aplicación -> response DTO.
- [x] 3.3 Mantener contratos HTTP existentes (`/api/*`, payloads, códigos de estado) sin cambios funcionales.

## 4. Persistence Adapter Alignment

- [x] 4.1 Actualizar adapters de persistencia para mapear entre modelos internos y tablas SQLModel.
- [x] 4.2 Eliminar cualquier lógica de negocio duplicada fuera del dominio (mantener solo mapeo/persistencia).
- [x] 4.3 Verificar paridad funcional entre in-memory y SQLModel con tests de contrato.

## 5. Architecture Guardrails

- [x] 5.1 Agregar tests de arquitectura que bloqueen imports prohibidos por capa.
- [x] 5.2 Integrar esos checks en la suite estándar (`make test`/CI).
- [x] 5.3 Documentar reglas de dependencia y estructura final esperada para futuros cambios.

## 6. Lightweight CQRS

- [x] 6.1 Definir handlers/puertos de comandos (write side) para operaciones mutables de Kanban.
- [x] 6.2 Definir handlers/puertos de consultas (read side) para lecturas de Kanban.
- [x] 6.3 Adaptar API adapters para invocar command/query handlers sin cambiar contrato HTTP.
- [x] 6.4 Agregar tests unitarios que validen la separación command/query.

## 7. Validation and Migration Closure

- [x] 7.1 Ejecutar `ruff`, `mypy`, `pytest` con la migración completa aplicada.
- [x] 7.2 Validar OpenSpec `apply` con tareas 100% completas.
- [x] 7.3 Preparar cambio para archive solo cuando se demuestre cumplimiento DDD/Hex estricto.
