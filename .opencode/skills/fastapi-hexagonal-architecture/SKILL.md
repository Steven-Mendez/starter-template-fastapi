---
name: fastapi-hexagonal-architecture
description: Design, review, and refactor FastAPI applications using Hexagonal Architecture, keeping FastAPI, databases, ORMs, queues, and cloud SDKs at the edges while preserving a testable business core.
license: MIT
compatibility: opencode
metadata:
  framework: fastapi
  architecture: hexagonal
  also_known_as: ports-and-adapters
  language: python
---

# FastAPI Hexagonal Architecture Skill

## Purpose

Use this skill when creating, reviewing, or refactoring a FastAPI application that should follow Hexagonal Architecture, also known as Ports and Adapters.

A good hexagonal FastAPI application is not "FastAPI with many folders." It is an application where FastAPI is only one adapter around a business core that can be tested, used, and evolved without depending on HTTP, databases, ORMs, queues, cloud SDKs, or external APIs.

The business core should be usable from:

- FastAPI routes
- CLI commands
- background workers
- batch jobs
- message consumers
- tests
- other Python programs

FastAPI is delivery. SQLAlchemy is persistence. Stripe, SendGrid, Redis, Kafka, S3, and similar tools are infrastructure. The domain and application layers are the business system.

## When to Use This Skill

Use this skill when the user asks to:

- create a FastAPI project with hexagonal architecture
- refactor an existing FastAPI app into ports and adapters
- move business logic out of routes
- separate domain, application, infrastructure, and API layers
- design use cases, ports, adapters, repositories, or units of work
- improve testability of FastAPI services
- introduce repository and unit-of-work patterns
- review whether a project is truly hexagonal
- decide whether hexagonal architecture is appropriate for a service

## Main Architectural Rule

Dependencies must point inward.

Correct direction:

```text
api -> application -> domain
infrastructure -> application/domain
```

Incorrect direction:

```text
domain -> infrastructure
domain -> api
application -> api
application -> concrete infrastructure
application -> FastAPI Depends
application -> SQLAlchemy session
```

The domain layer should depend on almost nothing.

## Mental Model

Think of the system like this:

```text
Outside world
    ↓
FastAPI router / CLI / worker / message consumer
    ↓
Application use case
    ↓
Domain model
    ↓
Port interface
    ↓
Adapter implementation
    ↓
Database / Redis / S3 / payment API / email provider
```

A bad version:

```text
Endpoint -> SQLAlchemy model -> database session -> business logic mixed in route
```

A better version:

```text
Endpoint -> use case -> domain entity -> repository port -> SQLAlchemy repository adapter
```

## Recommended Structure

For a medium-sized FastAPI service, prefer:

```text
app/
  main.py
  api/
    __init__.py
    error_handlers.py
    dependencies.py
    v1/
      __init__.py
      router.py
      routes/
        orders.py
        customers.py
        payments.py
      schemas/
        orders.py
        customers.py
        payments.py
  application/
    __init__.py
    commands/
      place_order.py
      cancel_order.py
    queries/
      get_order.py
      list_orders.py
    use_cases/
      place_order.py
      cancel_order.py
      get_order.py
    ports/
      order_repository.py
      payment_gateway.py
      email_sender.py
      event_publisher.py
      unit_of_work.py
    dto.py
    exceptions.py
  domain/
    __init__.py
    order/
      entity.py
      value_objects.py
      events.py
      exceptions.py
      rules.py
    customer/
      entity.py
      value_objects.py
    shared/
      money.py
      email.py
  infrastructure/
    __init__.py
    config.py
    database/
      session.py
      models.py
      migrations/
      mappers.py
      sqlalchemy_unit_of_work.py
    repositories/
      sqlalchemy_order_repository.py
      sqlalchemy_customer_repository.py
    external/
      stripe_payment_gateway.py
      sendgrid_email_sender.py
      http_product_catalog.py
    messaging/
      kafka_event_publisher.py
tests/
  unit/
    domain/
    application/
  integration/
    repositories/
    api/
  e2e/
```

For a smaller service, use fewer folders:

```text
app/
  main.py
  api/
  application/
  domain/
  infrastructure/
```

Do not create excessive layers for simple CRUD. Use architecture to control complexity, not to hide simplicity.

## Module-First Alternative

For larger systems, prefer bounded contexts or vertical slices:

```text
app/
  modules/
    orders/
      domain/
        order.py
        events.py
        exceptions.py
      application/
        place_order.py
        cancel_order.py
        ports.py
      infrastructure/
        sqlalchemy_repository.py
        models.py
        mapper.py
      api/
        routes.py
        schemas.py
        dependencies.py
    payments/
      domain/
      application/
      infrastructure/
      api/
```

This avoids giant global folders where unrelated features are mixed together.

## Domain Layer Rules

The domain layer contains business concepts, business rules, invariants, entities, value objects, domain services, domain events, and domain exceptions.

The domain layer must not know about:

- FastAPI
- Depends
- HTTPException
- Pydantic API schemas
- SQLAlchemy sessions
- ORM models
- JSON responses
- Redis
- Kafka
- S3
- environment variables
- background tasks
- OAuth libraries
- cloud SDKs
- payment SDKs
- email providers

The domain layer may contain:

- entities
- value objects
- domain exceptions
- domain events
- pure business services
- business rules
- standard library imports
- small pure libraries, when justified

Example:

```python
# app/domain/order/entity.py
from dataclasses import dataclass, field
from decimal import Decimal
from enum import Enum
from uuid import UUID, uuid4


class OrderStatus(str, Enum):
    DRAFT = "draft"
    CONFIRMED = "confirmed"
    CANCELLED = "cancelled"


@dataclass
class OrderItem:
    product_id: UUID
    quantity: int
    unit_price: Decimal

    def total(self) -> Decimal:
        return self.unit_price * self.quantity


@dataclass
class Order:
    id: UUID
    customer_id: UUID
    items: list[OrderItem] = field(default_factory=list)
    status: OrderStatus = OrderStatus.DRAFT

    @classmethod
    def new(cls, customer_id: UUID) -> "Order":
        return cls(id=uuid4(), customer_id=customer_id)

    def add_item(self, item: OrderItem) -> None:
        if self.status != OrderStatus.DRAFT:
            raise ValueError("Cannot modify a non-draft order")
        if item.quantity <= 0:
            raise ValueError("Quantity must be positive")
        self.items.append(item)

    def total(self) -> Decimal:
        return sum((item.total() for item in self.items), Decimal("0"))

    def confirm(self) -> None:
        if not self.items:
            raise ValueError("Cannot confirm an empty order")
        self.status = OrderStatus.CONFIRMED
```

This entity has no FastAPI, no SQLAlchemy, no HTTP, and no ORM dependency.

## Application Layer Rules

The application layer coordinates use cases.

It answers questions like:

- What should happen when a customer places an order?
- What should happen when a payment succeeds?
- What should happen when a user requests a password reset?
- What should happen when an order is cancelled?

The application layer should contain orchestration, not low-level infrastructure.

It may depend on:

- domain objects
- command/query DTOs
- application exceptions
- port interfaces

It must not directly depend on:

- FastAPI
- Depends
- Request
- Response
- HTTPException
- SQLAlchemy
- httpx
- boto3
- Redis clients
- Kafka clients
- Stripe SDKs
- SendGrid SDKs

Example:

```python
# app/application/use_cases/place_order.py
from dataclasses import dataclass
from uuid import UUID

from app.application.ports.order_repository import OrderRepository
from app.application.ports.product_catalog import ProductCatalog
from app.application.ports.unit_of_work import UnitOfWork
from app.domain.order.entity import Order, OrderItem


@dataclass(frozen=True)
class PlaceOrderItemCommand:
    product_id: UUID
    quantity: int


@dataclass(frozen=True)
class PlaceOrderCommand:
    customer_id: UUID
    items: list[PlaceOrderItemCommand]


class PlaceOrderUseCase:
    def __init__(
        self,
        orders: OrderRepository,
        products: ProductCatalog,
        uow: UnitOfWork,
    ) -> None:
        self.orders = orders
        self.products = products
        self.uow = uow

    async def execute(self, command: PlaceOrderCommand) -> UUID:
        order = Order.new(customer_id=command.customer_id)
        for item in command.items:
            product = await self.products.get_by_id(item.product_id)
            order.add_item(
                OrderItem(
                    product_id=product.id,
                    quantity=item.quantity,
                    unit_price=product.price,
                )
            )
        order.confirm()
        await self.orders.save(order)
        await self.uow.commit()
        return order.id
```

The use case should not know whether it was called by HTTP, CLI, a worker, a message consumer, or a test.

## Ports

A port is an interface the application uses to communicate with the outside world.

Use Python `Protocol` or abstract base classes.

Name ports after business capabilities, not technologies.

Good names:

- OrderRepository
- PaymentGateway
- EmailSender
- InvoiceStorage
- EventPublisher
- ProductCatalog
- UnitOfWork
- Clock
- IdGenerator

Bad names:

- PostgresOrderInterface
- StripeClientInterface
- SMTPService
- S3Uploader
- SQLAlchemyThing

The application should say what it needs. Infrastructure decides how to provide it.

Example repository port:

```python
# app/application/ports/order_repository.py
from typing import Protocol
from uuid import UUID

from app.domain.order.entity import Order


class OrderRepository(Protocol):
    async def get_by_id(self, order_id: UUID) -> Order | None:
        ...

    async def save(self, order: Order) -> None:
        ...
```

Example payment port:

```python
# app/application/ports/payment_gateway.py
from decimal import Decimal
from typing import Protocol
from uuid import UUID


class PaymentGateway(Protocol):
    async def charge(
        self,
        customer_id: UUID,
        amount: Decimal,
        currency: str,
    ) -> str:
        ...
```

Example email port:

```python
# app/application/ports/email_sender.py
from typing import Protocol


class EmailSender(Protocol):
    async def send(
        self,
        to: str,
        subject: str,
        body: str,
    ) -> None:
        ...
```

## Adapters

An adapter implements a port using concrete technology.

Examples:

- `SQLAlchemyOrderRepository` implements `OrderRepository`
- `StripePaymentGateway` implements `PaymentGateway`
- `SendGridEmailSender` implements `EmailSender`
- `S3InvoiceStorage` implements `InvoiceStorage`
- `RedisCache` implements `Cache`
- `KafkaEventPublisher` implements `EventPublisher`

Example SQLAlchemy adapter:

```python
# app/infrastructure/repositories/sqlalchemy_order_repository.py
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.ports.order_repository import OrderRepository
from app.domain.order.entity import Order
from app.infrastructure.database.mappers import (
    order_domain_to_model,
    order_model_to_domain,
)
from app.infrastructure.database.models import OrderModel


class SQLAlchemyOrderRepository(OrderRepository):
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_by_id(self, order_id: UUID) -> Order | None:
        result = await self.session.execute(
            select(OrderModel).where(OrderModel.id == order_id)
        )
        model = result.scalar_one_or_none()
        if model is None:
            return None
        return order_model_to_domain(model)

    async def save(self, order: Order) -> None:
        model = order_domain_to_model(order)
        await self.session.merge(model)
```

The adapter depends on the application port and domain model. The domain does not depend on the adapter.

## FastAPI as an Inbound Adapter

FastAPI is a driving adapter. It receives HTTP requests, validates input, calls use cases, and maps results or errors back to HTTP responses.

FastAPI routes should mostly do four things:

1. Accept HTTP input.
2. Convert Pydantic request data into application commands or queries.
3. Call a use case.
4. Convert the result into an HTTP response.

Routes should not:

- open transactions manually
- run complex business rules
- call SQLAlchemy directly
- call Stripe directly
- call external APIs directly
- build domain decisions inline
- contain many unrelated branches

Example:

```python
# app/api/v1/routes/orders.py
from fastapi import APIRouter, Depends, status

from app.api.v1.dependencies import get_place_order_use_case
from app.api.v1.schemas.orders import PlaceOrderRequest, PlaceOrderResponse
from app.application.use_cases.place_order import (
    PlaceOrderCommand,
    PlaceOrderItemCommand,
    PlaceOrderUseCase,
)

router = APIRouter(prefix="/orders", tags=["orders"])


@router.post(
    "",
    response_model=PlaceOrderResponse,
    status_code=status.HTTP_201_CREATED,
)
async def place_order(
    request: PlaceOrderRequest,
    use_case: PlaceOrderUseCase = Depends(get_place_order_use_case),
) -> PlaceOrderResponse:
    order_id = await use_case.execute(
        PlaceOrderCommand(
            customer_id=request.customer_id,
            items=[
                PlaceOrderItemCommand(
                    product_id=item.product_id,
                    quantity=item.quantity,
                )
                for item in request.items
            ],
        )
    )
    return PlaceOrderResponse(order_id=order_id)
```

## Pydantic Schemas Stay at the Edge

Pydantic request and response models normally belong to the API adapter. They are not the domain model.

Correct flow:

```text
API schema -> application command -> domain entity
domain result -> API response schema
```

Avoid:

```python
# Bad
from pydantic import BaseModel


class Order(BaseModel):
    ...
```

unless this is an intentional shortcut for a very simple service.

## Database Models Are Not Domain Models

Do not treat SQLAlchemy models as domain entities.

Bad:

```python
# Bad: business rule inside ORM model
class OrderModel(Base):
    ...

    def confirm(self) -> None:
        ...
```

Better:

```text
OrderModel = persistence representation
Order = domain representation
mapper = translation between both
```

This mapping can feel repetitive, but it protects the business model from persistence concerns. For simple CRUD services, this separation may be too much ceremony. For complex business systems, it usually pays off.

## Unit of Work

A Unit of Work coordinates a transaction. The use case should not need to know about database sessions.

Port:

```python
# app/application/ports/unit_of_work.py
from typing import Protocol


class UnitOfWork(Protocol):
    async def commit(self) -> None:
        ...

    async def rollback(self) -> None:
        ...
```

Adapter:

```python
# app/infrastructure/database/sqlalchemy_unit_of_work.py
from sqlalchemy.ext.asyncio import AsyncSession


class SQLAlchemyUnitOfWork:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def commit(self) -> None:
        await self.session.commit()

    async def rollback(self) -> None:
        await self.session.rollback()
```

Bad:

```python
# Bad: use case depends on SQLAlchemy
class PlaceOrderUseCase:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
```

Good:

```python
# Good: use case depends on a port
class PlaceOrderUseCase:
    def __init__(self, orders: OrderRepository, uow: UnitOfWork) -> None:
        self.orders = orders
        self.uow = uow
```

## Dependency Injection and Composition

FastAPI dependencies should mostly live at the API/infrastructure boundary. The application code must not call `Depends`. FastAPI calls `Depends`.

Bad:

```python
# Bad: FastAPI leaks into application layer
class PlaceOrderUseCase:
    def __init__(self, repo=Depends(get_repo)) -> None:
        self.repo = repo
```

Good:

```python
# Good: application code receives dependencies normally
class PlaceOrderUseCase:
    def __init__(self, repo: OrderRepository) -> None:
        self.repo = repo
```

Composition example:

```python
# app/api/v1/dependencies.py
from collections.abc import AsyncGenerator

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.use_cases.place_order import PlaceOrderUseCase
from app.infrastructure.database.session import async_session_factory
from app.infrastructure.database.sqlalchemy_unit_of_work import SQLAlchemyUnitOfWork
from app.infrastructure.external.http_product_catalog import HTTPProductCatalog
from app.infrastructure.repositories.sqlalchemy_order_repository import (
    SQLAlchemyOrderRepository,
)


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    async with async_session_factory() as session:
        yield session


async def get_place_order_use_case(
    session: AsyncSession = Depends(get_session),
) -> PlaceOrderUseCase:
    orders = SQLAlchemyOrderRepository(session)
    products = HTTPProductCatalog()
    uow = SQLAlchemyUnitOfWork(session)
    return PlaceOrderUseCase(
        orders=orders,
        products=products,
        uow=uow,
    )
```

This is the composition point.

## Error Handling

Domain and application layers should raise meaningful exceptions. FastAPI maps those exceptions to HTTP responses.

Domain exceptions:

```python
# app/domain/exceptions.py
class DomainError(Exception):
    pass


class BusinessRuleViolation(DomainError):
    pass


class EmptyOrderCannotBeConfirmed(BusinessRuleViolation):
    pass
```

Application exceptions:

```python
# app/application/exceptions.py
class UseCaseError(Exception):
    pass


class OrderNotFound(UseCaseError):
    pass
```

Do not raise `HTTPException` from the domain or application layer unless the project intentionally accepts FastAPI coupling.

## Validation Placement

There are several kinds of validation.

Syntax validation:

- Is this a UUID?
- Is quantity an integer?
- Is the field present?
- Is the string shaped like an email?

Place this in Pydantic API schemas.

Application validation:

- Does this user exist?
- Can this user perform this action?
- Is the referenced product available?

Place this in use cases.

Business invariant validation:

- An order cannot be confirmed without items.
- A cancelled invoice cannot be paid.
- A discount cannot exceed the order total.

Place this in domain objects.

Do not put all validation in Pydantic. Pydantic validates data shape. It should not become the business brain of the system.

## Authentication and Authorization

Authentication often starts in the FastAPI layer.

```text
JWT token -> FastAPI dependency -> CurrentUser object
```

Business authorization belongs in the use case or domain when it is business-specific.

Example command:

```python
from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True)
class CancelOrderCommand:
    order_id: UUID
    requested_by_user_id: UUID
```

HTTP-level authentication stays at the edge. Business-level authorization belongs in the application or domain layer.

## Commands and Queries

For more complex systems, separate writes and reads.

Write examples:

- PlaceOrderCommand
- PlaceOrderUseCase
- CancelOrderCommand
- CancelOrderUseCase

Read examples:

- GetOrderQuery
- GetOrderUseCase
- ListOrdersQuery
- ListOrdersUseCase

Sometimes reads do not need rich domain models. A query handler can use a read repository that returns DTOs.

## Domain Events

In larger systems, domain events can keep use cases cleaner.

Example event:

```python
# app/domain/order/events.py
from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True)
class OrderConfirmed:
    order_id: UUID
    customer_id: UUID
```

Domain events should not directly call Kafka, Redis, Celery, HTTP clients, or email providers.

## Configuration

Configuration belongs in infrastructure or app setup, not in domain.

Example:

```python
# app/infrastructure/config.py
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str
    stripe_api_key: str
    sendgrid_api_key: str

    model_config = {
        "env_file": ".env",
    }


settings = Settings()
```

Use configuration at composition time:

```python
payment_gateway = StripePaymentGateway(api_key=settings.stripe_api_key)
```

Do not do this inside domain:

```python
# Bad
import os

STRIPE_API_KEY = os.getenv("STRIPE_API_KEY")
```

## Async Design

FastAPI supports async endpoints, and many database and HTTP libraries also support async.

Common valid options:

- Fully async: async FastAPI route, async use case, async repository, async SQLAlchemy session, async HTTP client
- Mostly sync: sync domain, sync use case, sync repository, sync SQLAlchemy session

Avoid careless mixing:

- async route calling blocking database driver directly
- async use case doing slow blocking I/O
- domain methods becoming async without doing real I/O

Domain methods like `order.confirm()` should normally remain synchronous.

## Testing Strategy

A good hexagonal FastAPI app is easy to test at several levels.

Domain unit tests:

- no database
- no FastAPI
- usually no mocks

Application use-case tests:

- use fake adapters
- verify use-case orchestration
- verify ports are called through abstractions

Integration tests:

- SQLAlchemy repository with a test database
- Redis adapter with test Redis
- Stripe adapter with mocked HTTP server
- Kafka publisher with test broker or contract tests

API tests:

- test the HTTP contract
- use FastAPI dependency overrides where useful
- keep detailed business-rule tests in domain and application tests

## main.py

Keep `main.py` boring.

```python
# app/main.py
from fastapi import FastAPI

from app.api.error_handlers import register_error_handlers
from app.api.v1.router import api_router


def create_app() -> FastAPI:
    app = FastAPI(
        title="Order Service",
        version="1.0.0",
    )
    app.include_router(api_router, prefix="/v1")
    register_error_handlers(app)
    return app


app = create_app()
```

`main.py` should assemble the app, not contain business logic.

## CRUD vs Real Domain Logic

Not every FastAPI app needs heavy hexagonal architecture.

A simple CRUD app may be fine with:

```text
app/
  main.py
  routers/
  schemas/
  models/
  database.py
```

Use hexagonal architecture when the project has:

- complex business rules
- multiple external systems
- high testing needs
- long-lived codebase
- multiple input channels
- batch jobs plus HTTP API
- message consumers
- complex transactions
- expected database or provider changes

Rule:

```text
Do not add architecture to hide simplicity.
Use architecture to control complexity.
```

## Acceptable Shortcuts

Perfect purity is not always required.

Acceptable shortcuts when intentional:

- use Pydantic for simple application DTOs if FastAPI concerns do not leak
- use SQLModel or SQLAlchemy models directly for simple CRUD
- skip Unit of Work for simple read-only services
- use fewer folders for prototypes
- map only where the separation provides value

The problem is not using SQLAlchemy, Pydantic, or FastAPI. The problem is letting those tools define the business architecture.

## Anti-Patterns

Anti-pattern 1: Folder-only architecture.

```python
@router.post("/orders")
async def create_order(session: Session = Depends(get_session)):
    order = OrderModel(...)
    session.add(order)
    await stripe.charge(...)
    await session.commit()
```

Anti-pattern 2: Anemic pass-through use cases.

```python
class CreateUserUseCase:
    def __init__(self, repo):
        self.repo = repo

    async def execute(self, data):
        return await self.repo.create(data)
```

Anti-pattern 3: Too many ports.

```text
CreateUserPort
UpdateUserPort
DeleteUserPort
FindUserPort
ListUsersPort
CheckUserExistsPort
```

Better:

```text
UserRepository
```

Anti-pattern 4: Domain importing infrastructure.

```python
from app.infrastructure.database.models import OrderModel
```

Anti-pattern 5: Use case returning FastAPI response.

```python
return JSONResponse(...)
```

Anti-pattern 6: Generic service objects with too many methods.

```text
OrderService
UserService
PaymentService
```

Better:

```text
PlaceOrderUseCase
CancelOrderUseCase
CapturePaymentUseCase
RefundPaymentUseCase
```

Use-case names should communicate intent.

## Review Checklist

When reviewing a FastAPI codebase, check:

- Are FastAPI routes thin?
- Does the domain layer avoid FastAPI imports?
- Does the domain layer avoid SQLAlchemy imports?
- Does the application layer avoid FastAPI `Depends`?
- Does the application layer avoid concrete infrastructure?
- Do use cases depend on ports rather than concrete adapters?
- Are Pydantic API schemas kept near the API layer?
- Are SQLAlchemy models kept in infrastructure?
- Are ORM models separate from domain entities when business logic is meaningful?
- Are business exceptions translated at the API boundary?
- Are repositories hiding persistence details?
- Is Unit of Work used when transactions matter?
- Can use cases run with fake adapters?
- Can API tests override FastAPI dependencies?
- Are ports named after capabilities rather than technologies?
- Are business rules in domain objects or domain services?
- Is the folder structure supporting dependency direction rather than just creating many folders?

## Practical Import Checks

Suggest commands like these when reviewing the project:

```bash
grep -R "fastapi" app/domain
grep -R "sqlalchemy" app/domain
grep -R "Depends" app/application
grep -R "HTTPException" app/application app/domain
grep -R "sqlalchemy" app/application
```

Expected result: no matches, unless there is a deliberate and documented exception.

## Output Behavior

When using this skill, produce answers in this style:

1. Start with the architectural decision.
2. Show the target folder/file structure.
3. Create or modify only the necessary files.
4. Keep routers thin.
5. Put business rules in domain objects or domain services.
6. Put orchestration in use cases.
7. Put interfaces in ports.
8. Put concrete integrations in infrastructure adapters.
9. Add tests for domain and application logic.
10. Mention any intentional shortcuts or trade-offs.

When generating code, prefer complete, minimal examples over large theoretical explanations.

## Final Summary

A good hexagonal FastAPI app treats FastAPI as an adapter, not as the application.

The business core should be usable without HTTP, without a database, and without the framework.
