## Context

El proyecto actual funciona bajo un patrón que intenta ser Arquitectura Limpia/Hexagonal y CQRS, pero peca de varios antipatrones: entidades anémicas (`@dataclass` de solo datos), repositorios estilo Dios/CRUD, y escritura sin protección transaccional en flujos compuestos.

## Goals / Non-Goals

**Goals:**
- Cumplimiento estricto de Arquitectura Hexagonal y DDD.
- Encapsular la lógica de dominio en de ricas entidades (ej. que `Board` valide movimientos y gestione sus columnas).
- Proveer Atomicidad (ACID) en los Command Handlers mediante un patrón Unit of Work común para cualquier adaptador (ej: SQLite, in-memory).
- Reducir el `KanbanRepository` a Repository-per-Aggregate y eliminar acoplamiento directo a CRUD de sub-entidades.

**Non-Goals:**
- Modificar las firmas HTTP de la API REST o los modelos Pydantic esquemáticos (solamente las capas de subyacentes se verán afectadas).
- Añadir base de datos externa tipo Postgres o Redis; continuaremos soportando las primitivas de `sqlmodel` (SQLite) y en RAM.

## Decisions

- **Rich Entities vs Anemic Data Classes**: Los servicios procedimentales como `card_movement.py` se absorberán como métodos nativos dentro de un Root Entity o Aggregate. El Command Handler solo llama a `board.move_card(...)`.
- **Patrón `UnitOfWork`**: Se definirá un contrato abstract unit of work intermedio que inyecte el repositorio. Los Handlers invocarán algo parecido a `with uow: uow.boards.update(board)`.
- **Eliminación de `KanbanUseCases`**: Al no estar usándose en los enrutadores por optar por `KanbanCommandHandlers` (CQRS ligero), todo caso de uso redundante e híbrido será descartado.

## Risks / Trade-offs

- **[Risk] Mayor complejidad transaccional para SQLite en SQLModel** -> Mitigación: Implementaremos el `UnitOfWork` usando context managers que engloben a `Session.commit()` y `Session.rollback()` explícitamente.
- **[Risk] Migración de un Repositorio Único a Múltiples Aggregates** -> Inicialmente trataremos al `Board` como único Aggregate Root para simplificar la transición, persistiendo toda su red de entidades (columnas/tarjetas) en la unidad de trabajo.
