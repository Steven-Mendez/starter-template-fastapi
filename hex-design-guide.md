A good hexagonal architecture FastAPI application is not “FastAPI with many folders.” It is an application where FastAPI is only one adapter around a business core that can be tested, used, and evolved without depending on HTTP, databases, ORMs, queues, or cloud SDKs.

Hexagonal architecture is also called Ports and Adapters. The central idea is that the application should be equally drivable by users, tests, batch jobs, scripts, message consumers, or other programs, while being isolated from runtime devices such as databases and external APIs. That framing comes from Alistair Cockburn’s original hexagonal architecture article.  ￼ FastAPI fits this style well because it has routers, dependency injection, request/response validation, and testing support, but those features should live mostly at the edges, not in the domain core. FastAPI’s own docs describe dependency injection as a simple way to integrate components, and its “bigger applications” guidance encourages splitting larger APIs into multiple files and routers.  ￼

⸻

1. The main idea

A well-designed hexagonal FastAPI app usually has this shape:

Outside world
    ↓
FastAPI router / CLI / worker / message consumer
    ↓
Application service / use case
    ↓
Domain model
    ↓
Port interface
    ↓
Adapter implementation
    ↓
Database / Redis / S3 / payment API / email provider

The most important rule:

Dependencies point inward.

That means:

FastAPI depends on application code.
Application code depends on domain code and port interfaces.
Infrastructure depends on application/domain contracts.
Domain code depends on almost nothing.

A bad version looks like this:

Endpoint → SQLAlchemy model → database session → business logic mixed in route

A better version looks like this:

Endpoint → use case → domain entity → repository port → SQLAlchemy repository adapter

⸻

2. The layers

A good FastAPI hexagonal architecture normally separates the code into these areas:

app/
  main.py
  api/
    v1/
      routes/
      schemas/
      dependencies.py
  application/
    use_cases/
    services/
    ports/
    dto.py
  domain/
    entities/
    value_objects/
    events/
    exceptions.py
    rules.py
  infrastructure/
    database/
    repositories/
    external_services/
    messaging/
    config.py
  tests/
    unit/
    integration/
    e2e/

The exact names can vary, but the responsibilities should stay clear.

⸻

3. Domain layer

The domain layer contains the business concepts and rules.

It should not know about:

FastAPI
Pydantic request models
SQLAlchemy sessions
HTTP status codes
JSON
Redis
Kafka
S3
environment variables
background tasks
OAuth libraries

It should contain things like:

User
Order
Invoice
Payment
Subscription
Money
EmailAddress
OrderStatus
DomainError
BusinessRuleViolation

Example:

# app/domain/entities/order.py
from dataclasses import dataclass, field
from decimal import Decimal
from enum import Enum
from uuid import UUID
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

This domain object has no FastAPI, no database, no HTTP, and no ORM dependency.

That is the point.

⸻

4. Application layer

The application layer coordinates use cases.

It answers questions like:

What should happen when a customer places an order?
What should happen when a payment succeeds?
What should happen when a user requests a password reset?

It should contain orchestration, not low-level infrastructure.

Example:

# app/application/use_cases/place_order.py
from dataclasses import dataclass
from uuid import UUID
from app.domain.entities.order import Order, OrderItem
from app.application.ports.order_repository import OrderRepository
from app.application.ports.product_catalog import ProductCatalog
from app.application.ports.unit_of_work import UnitOfWork
@dataclass
class PlaceOrderCommand:
    customer_id: UUID
    items: list[dict]
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
            product = await self.products.get_by_id(item["product_id"])
            order.add_item(
                OrderItem(
                    product_id=product.id,
                    quantity=item["quantity"],
                    unit_price=product.price,
                )
            )
        order.confirm()
        await self.orders.save(order)
        await self.uow.commit()
        return order.id

This layer may use ports such as:

OrderRepository
PaymentGateway
EmailSender
EventPublisher
UnitOfWork
Clock
IdGenerator
ProductCatalog

It should not directly use:

SQLAlchemy
httpx
boto3
FastAPI Request
FastAPI Depends

The application service should depend on interfaces, not concrete infrastructure. This is the same direction promoted by the repository and unit-of-work patterns in Architecture Patterns with Python: repository abstracts persistence, and unit of work abstracts atomic operations/transactions.  ￼

⸻

5. Ports

A port is an interface the application uses to communicate with the outside world.

In Python, ports are often represented with Protocol or abstract base classes.

Example repository port:

# app/application/ports/order_repository.py
from typing import Protocol
from uuid import UUID
from app.domain.entities.order import Order
class OrderRepository(Protocol):
    async def get_by_id(self, order_id: UUID) -> Order | None:
        ...
    async def save(self, order: Order) -> None:
        ...

Example payment gateway port:

# app/application/ports/payment_gateway.py
from typing import Protocol
from uuid import UUID
from decimal import Decimal
class PaymentGateway(Protocol):
    async def charge(
        self,
        customer_id: UUID,
        amount: Decimal,
        currency: str,
    ) -> str:
        ...

Example email port:

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

Good ports are named after business capabilities, not technologies.

Better:

PaymentGateway
EmailSender
OrderRepository
InvoiceStorage
EventPublisher

Worse:

StripeClientInterface
PostgresOrderInterface
SMTPService
S3Uploader

The application should say what it needs. Infrastructure decides how to provide it.

⸻

6. Adapters

An adapter implements a port using a concrete technology.

Examples:

SQLAlchemyOrderRepository implements OrderRepository
StripePaymentGateway implements PaymentGateway
SendGridEmailSender implements EmailSender
S3InvoiceStorage implements InvoiceStorage
RedisCache implements Cache
KafkaEventPublisher implements EventPublisher

Example SQLAlchemy adapter:

# app/infrastructure/repositories/sqlalchemy_order_repository.py
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.application.ports.order_repository import OrderRepository
from app.domain.entities.order import Order
from app.infrastructure.database.models import OrderModel
from app.infrastructure.database.mappers import order_model_to_domain, order_domain_to_model
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

Notice that the adapter depends on the application port and domain model.

The domain does not depend on the adapter.

⸻

7. FastAPI as an inbound adapter

FastAPI should be treated as a driving adapter.

It receives HTTP requests, validates input, calls use cases, and maps results/errors back to HTTP responses.

It should not contain the business rules.

Example:

# app/api/v1/routes/orders.py
from uuid import UUID
from fastapi import APIRouter, Depends, status
from app.api.v1.schemas.orders import PlaceOrderRequest, PlaceOrderResponse
from app.api.v1.dependencies import get_place_order_use_case
from app.application.use_cases.place_order import (
    PlaceOrderCommand,
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
                {
                    "product_id": item.product_id,
                    "quantity": item.quantity,
                }
                for item in request.items
            ],
        )
    )
    return PlaceOrderResponse(order_id=order_id)

The endpoint should mostly do four things:

1. Accept HTTP input.
2. Convert HTTP/Pydantic data into application command/query objects.
3. Call the use case.
4. Convert the result into an HTTP response.

It should not:

Open transactions manually.
Run complex business rules.
Call SQLAlchemy directly.
Call Stripe directly.
Build domain decisions inline.
Handle many unrelated branches.

FastAPI’s dependency injection system is useful here because you can assemble concrete adapters at the edge while keeping the core decoupled.  ￼

⸻

8. Pydantic schemas should stay at the edge

A common mistake is to use Pydantic models everywhere.

In a hexagonal FastAPI app, Pydantic request/response models usually belong to the API adapter.

Example:

# app/api/v1/schemas/orders.py
from pydantic import BaseModel, Field
from uuid import UUID
class PlaceOrderItemRequest(BaseModel):
    product_id: UUID
    quantity: int = Field(gt=0)
class PlaceOrderRequest(BaseModel):
    customer_id: UUID
    items: list[PlaceOrderItemRequest]
class PlaceOrderResponse(BaseModel):
    order_id: UUID

These models are for HTTP input/output.

They are not your domain model.

Avoid this:

# Bad: domain entity inherits from Pydantic API schema
class Order(BaseModel):
    ...

Better:

API schema → application command → domain entity
domain result → API response schema

This gives you freedom to change the public API without rewriting your business model.

⸻

9. Database models are not domain models

Another common mistake is treating SQLAlchemy models as domain entities.

Bad:

# Business rule inside ORM model tightly coupled to database mapping
class OrderModel(Base):
    ...
    def confirm(self):
        ...

Better:

OrderModel = persistence representation
Order = domain representation
Mapper = translation between them

Example mapper:

# app/infrastructure/database/mappers.py
from app.domain.entities.order import Order, OrderItem, OrderStatus
from app.infrastructure.database.models import OrderModel, OrderItemModel
def order_model_to_domain(model: OrderModel) -> Order:
    return Order(
        id=model.id,
        customer_id=model.customer_id,
        status=OrderStatus(model.status),
        items=[
            OrderItem(
                product_id=item.product_id,
                quantity=item.quantity,
                unit_price=item.unit_price,
            )
            for item in model.items
        ],
    )
def order_domain_to_model(order: Order) -> OrderModel:
    return OrderModel(
        id=order.id,
        customer_id=order.customer_id,
        status=order.status.value,
        items=[
            OrderItemModel(
                product_id=item.product_id,
                quantity=item.quantity,
                unit_price=item.unit_price,
            )
            for item in order.items
        ],
    )

This mapping feels repetitive, but it gives you separation.

For small CRUD services, you may decide this is too much ceremony. For complex business systems, the separation pays off.

FastAPI’s SQL database documentation shows direct SQLModel/SQLAlchemy-style integrations as a practical default, but hexagonal architecture usually adds a repository boundary so persistence details do not leak into use cases.  ￼

⸻

10. Unit of Work

A Unit of Work coordinates a transaction.

Without it, your use case may need to know about database sessions.

Bad:

class PlaceOrderUseCase:
    def __init__(self, session: AsyncSession):
        self.session = session
    async def execute(self, command):
        ...
        await self.session.commit()

Better:

class PlaceOrderUseCase:
    def __init__(self, orders: OrderRepository, uow: UnitOfWork):
        self.orders = orders
        self.uow = uow
    async def execute(self, command):
        ...
        await self.orders.save(order)
        await self.uow.commit()

Port:

# app/application/ports/unit_of_work.py
from typing import Protocol
class UnitOfWork(Protocol):
    async def commit(self) -> None:
        ...
    async def rollback(self) -> None:
        ...

Adapter:

# app/infrastructure/database/sqlalchemy_unit_of_work.py
from sqlalchemy.ext.asyncio import AsyncSession
class SQLAlchemyUnitOfWork:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
    async def commit(self) -> None:
        await self.session.commit()
    async def rollback(self) -> None:
        await self.session.rollback()

In more advanced implementations, the Unit of Work owns the session and repositories:

class SQLAlchemyUnitOfWork:
    def __init__(self, session_factory):
        self.session_factory = session_factory
    async def __aenter__(self):
        self.session = self.session_factory()
        self.orders = SQLAlchemyOrderRepository(self.session)
        return self
    async def __aexit__(self, *args):
        await self.rollback()
        await self.session.close()
    async def commit(self):
        await self.session.commit()
    async def rollback(self):
        await self.session.rollback()

The Unit of Work pattern is commonly used with Repository to decouple application services from persistence and to group operations into atomic transactions.  ￼

⸻

11. Dependency injection composition

FastAPI dependencies should mostly live in the API/infrastructure boundary.

Example:

# app/api/v1/dependencies.py
from collections.abc import AsyncGenerator
from sqlalchemy.ext.asyncio import AsyncSession
from app.infrastructure.database.session import async_session_factory
from app.infrastructure.repositories.sqlalchemy_order_repository import (
    SQLAlchemyOrderRepository,
)
from app.infrastructure.repositories.http_product_catalog import HTTPProductCatalog
from app.infrastructure.database.sqlalchemy_unit_of_work import SQLAlchemyUnitOfWork
from app.application.use_cases.place_order import PlaceOrderUseCase
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

This is the composition point.

The application code does not call Depends.

FastAPI calls Depends.

That distinction matters.

Bad:

# Bad: FastAPI leaks into application layer
class PlaceOrderUseCase:
    def __init__(self, repo = Depends(get_repo)):
        ...

Good:

# Good: application code receives dependencies normally
class PlaceOrderUseCase:
    def __init__(self, repo: OrderRepository):
        ...

⸻

12. Recommended folder structure

For a medium-to-large FastAPI service:

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

For a smaller app, use fewer folders:

app/
  main.py
  api/
  application/
  domain/
  infrastructure/

Do not create fifteen layers for a simple CRUD app.

Hexagonal architecture is useful when you have meaningful business behavior, multiple integrations, complex tests, or expected long-term change.

⸻

13. Request lifecycle in a good design

Example: POST /orders

1. Client sends HTTP request.
2. FastAPI validates JSON with Pydantic request schema.
3. Router converts request schema into PlaceOrderCommand.
4. Router calls PlaceOrderUseCase.
5. Use case loads product data through ProductCatalog port.
6. Use case creates Order domain entity.
7. Domain object validates business rules.
8. Use case saves through OrderRepository port.
9. SQLAlchemyOrderRepository persists the data.
10. Use case commits through UnitOfWork.
11. Router returns Pydantic response schema.

The endpoint should not know how the order is persisted.

The use case should not know the request came from HTTP.

The domain should not know that FastAPI exists.

⸻

14. Error handling

Domain and application layers should raise meaningful application/domain exceptions.

Example:

# app/domain/exceptions.py
class DomainError(Exception):
    pass
class BusinessRuleViolation(DomainError):
    pass
class EmptyOrderCannotBeConfirmed(BusinessRuleViolation):
    pass

Application exception:

# app/application/exceptions.py
class UseCaseError(Exception):
    pass
class OrderNotFound(UseCaseError):
    pass

FastAPI maps those to HTTP:

# app/api/error_handlers.py
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from app.application.exceptions import OrderNotFound
from app.domain.exceptions import BusinessRuleViolation
def register_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(OrderNotFound)
    async def order_not_found_handler(
        request: Request,
        exc: OrderNotFound,
    ) -> JSONResponse:
        return JSONResponse(
            status_code=404,
            content={"detail": "Order not found"},
        )
    @app.exception_handler(BusinessRuleViolation)
    async def business_rule_handler(
        request: Request,
        exc: BusinessRuleViolation,
    ) -> JSONResponse:
        return JSONResponse(
            status_code=400,
            content={"detail": str(exc)},
        )

Do not raise HTTPException from your domain or use case unless you intentionally accept FastAPI coupling.

Bad:

# Bad inside domain/use case
raise HTTPException(status_code=404, detail="Order not found")

Good:

# Good inside use case
raise OrderNotFound(order_id)

Then the API adapter translates it to HTTP.

⸻

15. Testing strategy

A good hexagonal FastAPI app is easy to test at several levels.

Unit tests for domain

No database. No FastAPI. No mocks usually.

def test_cannot_confirm_empty_order():
    order = Order(id=uuid4(), customer_id=uuid4())
    with pytest.raises(ValueError):
        order.confirm()

These tests should be fast and numerous.

Unit tests for use cases

Use fake adapters.

class FakeOrderRepository:
    def __init__(self):
        self.saved = []
    async def save(self, order):
        self.saved.append(order)
    async def get_by_id(self, order_id):
        return None
class FakeUnitOfWork:
    def __init__(self):
        self.committed = False
    async def commit(self):
        self.committed = True
    async def rollback(self):
        pass

Test:

@pytest.mark.asyncio
async def test_place_order_saves_confirmed_order():
    orders = FakeOrderRepository()
    products = FakeProductCatalog()
    uow = FakeUnitOfWork()
    use_case = PlaceOrderUseCase(
        orders=orders,
        products=products,
        uow=uow,
    )
    order_id = await use_case.execute(command)
    assert order_id is not None
    assert len(orders.saved) == 1
    assert orders.saved[0].status == OrderStatus.CONFIRMED
    assert uow.committed is True

Integration tests for adapters

These test real infrastructure details.

SQLAlchemy repository with test database
Stripe adapter with mocked HTTP server
Redis adapter with test Redis
Kafka publisher with test broker or contract test

FastAPI’s documentation includes guidance for testing database-backed apps, and its dependency injection also makes it practical to override dependencies in tests.  ￼

API tests

These test the HTTP contract.

def test_place_order_returns_201(client):
    response = client.post(
        "/v1/orders",
        json={
            "customer_id": str(uuid4()),
            "items": [
                {
                    "product_id": str(uuid4()),
                    "quantity": 2,
                }
            ],
        },
    )
    assert response.status_code == 201
    assert "order_id" in response.json()

The API test should not need to verify every business rule. Business rules belong mostly in domain and use-case tests.

⸻

16. Good dependency direction

This is the most important design check.

Good:

api → application → domain
infrastructure → application/domain

Bad:

domain → infrastructure
application → FastAPI
application → SQLAlchemy
domain → Pydantic API schema
domain → HTTPException

A good import graph:

app/domain
  imports: standard library only, maybe small pure libraries
app/application
  imports: domain, ports, DTOs
app/infrastructure
  imports: application ports, domain, SQLAlchemy, Redis, httpx, cloud SDKs
app/api
  imports: FastAPI, Pydantic schemas, application use cases

A bad import graph:

app/domain/order.py imports fastapi.HTTPException
app/application/place_order.py imports sqlalchemy.ext.asyncio.AsyncSession
app/domain/user.py imports pydantic.BaseModel for API validation

⸻

17. Commands and queries

For more complex systems, separate writes and reads.

Write use case:

PlaceOrderCommand
PlaceOrderUseCase
CancelOrderCommand
CancelOrderUseCase

Read use case:

GetOrderQuery
GetOrderUseCase
ListOrdersQuery
ListOrdersUseCase

Sometimes reads do not need rich domain models. A query handler can use a read repository that returns DTOs.

Example:

@dataclass
class OrderSummaryDTO:
    id: UUID
    customer_id: UUID
    status: str
    total: Decimal

This is practical because not every read needs to reconstruct a full aggregate.

⸻

18. Domain events

In larger systems, domain events can keep use cases clean.

Example:

# app/domain/order/events.py
from dataclasses import dataclass
from uuid import UUID
@dataclass(frozen=True)
class OrderConfirmed:
    order_id: UUID
    customer_id: UUID

Domain entity:

@dataclass
class Order:
    ...
    events: list[object] = field(default_factory=list)
    def confirm(self) -> None:
        if not self.items:
            raise EmptyOrderCannotBeConfirmed()
        self.status = OrderStatus.CONFIRMED
        self.events.append(
            OrderConfirmed(
                order_id=self.id,
                customer_id=self.customer_id,
            )
        )

Use case:

await self.orders.save(order)
await self.uow.commit()
for event in order.events:
    await self.event_publisher.publish(event)

More advanced version: the Unit of Work collects events and publishes them after commit.

This avoids mixing side effects into domain logic.

⸻

19. Configuration

Configuration belongs in infrastructure or app setup, not in domain.

Example:

# app/infrastructure/config.py
from pydantic_settings import BaseSettings
class Settings(BaseSettings):
    database_url: str
    stripe_api_key: str
    sendgrid_api_key: str
    class Config:
        env_file = ".env"
settings = Settings()

Use it at composition time:

payment_gateway = StripePaymentGateway(api_key=settings.stripe_api_key)

Do not do this inside domain:

# Bad
import os
STRIPE_API_KEY = os.getenv("STRIPE_API_KEY")

⸻

20. Async design

FastAPI supports async endpoints, and many database and HTTP libraries also support async. A good design should be consistent.

Common options:

Fully async

async FastAPI route
async use case
async repository
async SQLAlchemy session
async httpx client

This is common for modern FastAPI apps.

Mostly sync

sync domain
sync use case
sync repository
sync SQLAlchemy session

This can be fine if the app is simple or uses sync infrastructure.

Avoid mixing carelessly:

async route calling blocking database driver directly
async use case doing slow blocking I/O

Domain logic itself usually does not need to be async. Domain methods like order.confirm() should remain synchronous unless they truly perform I/O, which they normally should not.

⸻

21. What belongs where

FastAPI router

Belongs here:

HTTP method
URL path
status code
request schema
response schema
Depends
auth extraction
HTTP error mapping

Does not belong here:

business decision logic
transaction rules
database queries
payment logic
email body policy

Application use case

Belongs here:

orchestration
transaction boundary
calling ports
coordinating domain objects
authorization at use-case level
application-specific validation

Does not belong here:

SQL queries
HTTP request parsing
Pydantic API response formatting
cloud SDK calls

Domain

Belongs here:

business invariants
entities
value objects
domain services
domain events
business exceptions

Does not belong here:

FastAPI
SQLAlchemy
Pydantic API models
Redis
Stripe SDK
email provider code

Infrastructure

Belongs here:

database models
repository implementations
external API clients
message broker clients
email clients
file storage
configuration

Does not belong here:

core business rules
HTTP response decisions

⸻

22. Authentication and authorization

Authentication often starts in the FastAPI layer.

Example:

JWT token → FastAPI dependency → CurrentUser object

But authorization may belong in the application layer if it is business-specific.

Example:

@dataclass
class CancelOrderCommand:
    order_id: UUID
    requested_by_user_id: UUID

Use case:

class CancelOrderUseCase:
    async def execute(self, command: CancelOrderCommand) -> None:
        order = await self.orders.get_by_id(command.order_id)
        if order is None:
            raise OrderNotFound(command.order_id)
        if order.customer_id != command.requested_by_user_id:
            raise NotAllowedToCancelOrder()
        order.cancel()
        await self.orders.save(order)
        await self.uow.commit()

API:

@router.post("/{order_id}/cancel")
async def cancel_order(
    order_id: UUID,
    current_user: CurrentUser = Depends(get_current_user),
    use_case: CancelOrderUseCase = Depends(get_cancel_order_use_case),
):
    await use_case.execute(
        CancelOrderCommand(
            order_id=order_id,
            requested_by_user_id=current_user.id,
        )
    )
    return Response(status_code=204)

HTTP-level authentication stays at the edge.

Business-level authorization lives in the use case or domain.

⸻

23. CRUD vs real domain logic

Not every FastAPI app needs heavy hexagonal architecture.

For simple CRUD:

create user
get user
update user
delete user

A thinner structure may be enough.

But use hexagonal architecture when you have:

complex business rules
multiple external systems
high testing needs
long-lived codebase
multiple input channels
batch jobs plus HTTP API
message consumers
complex transactions
expected database/provider changes

A good rule:

Do not add architecture to hide simplicity.
Use architecture to control complexity.

⸻

24. Example: complete mini design

Imagine an order service.

Domain

Order
OrderItem
Money
OrderStatus
OrderConfirmed
EmptyOrderCannotBeConfirmed

Application ports

OrderRepository
ProductCatalog
PaymentGateway
EmailSender
EventPublisher
UnitOfWork

Application use cases

PlaceOrderUseCase
CancelOrderUseCase
PayOrderUseCase
GetOrderUseCase

Inbound adapters

FastAPI REST API
CLI command
Kafka consumer
scheduled job

Outbound adapters

SQLAlchemyOrderRepository
HTTPProductCatalog
StripePaymentGateway
SendGridEmailSender
KafkaEventPublisher
SQLAlchemyUnitOfWork

The same PlaceOrderUseCase can be called by:

POST /orders
a CLI script
a batch import job
a message consumer
a test

That is the value of the architecture.

⸻

25. Anti-patterns

Anti-pattern 1: Folder-only architecture

Bad:

domain/
services/
repositories/

But inside:

@router.post("/orders")
async def create_order(session: Session = Depends(get_session)):
    order = OrderModel(...)
    session.add(order)
    await stripe.charge(...)
    await session.commit()

This is not hexagonal architecture. It is just folders.

Anti-pattern 2: Anemic pass-through use cases

Bad:

class CreateUserUseCase:
    def __init__(self, repo):
        self.repo = repo
    async def execute(self, data):
        return await self.repo.create(data)

If every use case is just repo.create, the architecture may be unnecessary.

Anti-pattern 3: Too many ports

Bad:

CreateUserPort
UpdateUserPort
DeleteUserPort
FindUserPort
ListUsersPort
CheckUserExistsPort

Better:

UserRepository

Ports should represent meaningful boundaries, not every function.

Anti-pattern 4: Domain importing infrastructure

Bad:

from app.infrastructure.database.models import OrderModel

inside domain.

Anti-pattern 5: Use case returning FastAPI response

Bad:

return JSONResponse(...)

from application layer.

Anti-pattern 6: Overusing generic service names

Bad:

OrderService
UserService
PaymentService

with hundreds of methods.

Better:

PlaceOrderUseCase
CancelOrderUseCase
CapturePaymentUseCase
RefundPaymentUseCase

Use-case names communicate intent.

⸻

26. What a good main.py looks like

# app/main.py
from fastapi import FastAPI
from app.api.v1.router import api_router
from app.api.error_handlers import register_error_handlers
def create_app() -> FastAPI:
    app = FastAPI(
        title="Order Service",
        version="1.0.0",
    )
    app.include_router(api_router, prefix="/v1")
    register_error_handlers(app)
    return app
app = create_app()

Keep main.py boring.

It should assemble the app, not contain business logic.

⸻

27. What a good router aggregator looks like

# app/api/v1/router.py
from fastapi import APIRouter
from app.api.v1.routes import orders, customers, payments
api_router = APIRouter()
api_router.include_router(orders.router)
api_router.include_router(customers.router)
api_router.include_router(payments.router)

This aligns well with FastAPI’s router-based structure for bigger applications.  ￼

⸻

28. Testing dependency overrides

FastAPI makes it possible to override dependencies during tests.

Example:

def test_place_order(client, fake_place_order_use_case):
    app.dependency_overrides[get_place_order_use_case] = (
        lambda: fake_place_order_use_case
    )
    response = client.post(
        "/v1/orders",
        json={
            "customer_id": str(uuid4()),
            "items": [],
        },
    )
    assert response.status_code == 201

This is useful for API tests where you want to test HTTP behavior without hitting the real database.

But do not rely only on API tests. A good hexagonal app should have many fast unit tests around the domain and application layers.

⸻

29. Practical architecture rules

Use these rules as a checklist.

Rule 1: Domain has no framework imports

This should be true:

grep -R "fastapi" app/domain
# no results

Rule 2: Application has no database imports

Ideally:

grep -R "sqlalchemy" app/application
# no results

Rule 3: Use cases are callable without FastAPI

You should be able to do:

use_case = PlaceOrderUseCase(
    orders=fake_orders,
    products=fake_products,
    uow=fake_uow,
)
await use_case.execute(command)

No HTTP request required.

Rule 4: Infrastructure implements ports

Infrastructure should be replaceable.

SQLAlchemyOrderRepository → Postgres
InMemoryOrderRepository → tests
DynamoDBOrderRepository → alternative storage

Rule 5: API translates, it does not decide

Routers translate between HTTP and application.

They should not own business policy.

⸻

30. Good architecture by app size

Small app

app/
  main.py
  routers/
  schemas/
  models/
  database.py

This is acceptable for simple CRUD.

Medium app

app/
  api/
  application/
  domain/
  infrastructure/

Good balance.

Large app

Consider splitting by bounded context:

app/
  ordering/
    api/
    application/
    domain/
    infrastructure/
  billing/
    api/
    application/
    domain/
    infrastructure/
  identity/
    api/
    application/
    domain/
    infrastructure/

This is often better than one huge global domain/, application/, and infrastructure/.

For example:

app/
  modules/
    ordering/
      domain/
      application/
      infrastructure/
      api/
    payments/
      domain/
      application/
      infrastructure/
      api/

This keeps related code together.

⸻

31. Vertical slice plus hexagonal architecture

A very practical FastAPI structure is “vertical slices inside hexagonal boundaries.”

Example:

app/
  modules/
    orders/
      domain/
        order.py
        events.py
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

This avoids giant folders like:

repositories/
services/
models/
schemas/

where unrelated features are mixed together.

For large codebases, feature/module-first structure is often easier to maintain.

⸻

32. Example dependency flow in module style

orders/api/routes.py
  imports orders/application/place_order.py
orders/application/place_order.py
  imports orders/domain/order.py
  imports orders/application/ports.py
orders/infrastructure/sqlalchemy_repository.py
  imports orders/application/ports.py
  imports orders/domain/order.py
  imports sqlalchemy
orders/domain/order.py
  imports only standard library

That is healthy.

⸻

33. Where validation should happen

There are several kinds of validation.

Syntax validation

Example:

Is this a UUID?
Is quantity an integer?
Is email shaped like an email?

This belongs in Pydantic API schemas.

Application validation

Example:

Does this user exist?
Can this user perform this action?
Is the referenced product available?

This belongs in use cases.

Business invariant validation

Example:

An order cannot be confirmed without items.
A cancelled invoice cannot be paid.
A discount cannot exceed the order total.

This belongs in domain objects.

Do not put all validation in Pydantic.

Pydantic validates data shape. It should not become the business brain of the system.

⸻

34. DTOs vs domain objects vs schemas

You may have three kinds of objects:

API schema: HTTP input/output
Application DTO/command/query: use-case input/output
Domain entity/value object: business behavior

Example:

PlaceOrderRequest       # FastAPI/Pydantic
PlaceOrderCommand       # application dataclass
Order                   # domain entity
OrderModel              # SQLAlchemy database model

This may look verbose, but each object has a different reason to change.

API changes because public contract changes.
Command changes because use-case input changes.
Domain changes because business rules change.
Database model changes because persistence changes.

Keeping them separate avoids one change breaking all layers.

⸻

35. When to relax the rules

You do not need perfect purity everywhere.

Acceptable shortcuts:

Use Pydantic for simple application DTOs if it does not leak FastAPI concerns.
Use SQLModel for simple CRUD where domain logic is minimal.
Use direct repositories without Unit of Work for simple read-only services.
Use fewer layers for prototypes.

But be intentional.

The problem is not using SQLAlchemy or Pydantic. The problem is letting those tools define your business architecture.

⸻

36. A good mental model

Think of the system like this:

Domain:
  The business truth.
Application:
  The business process.
Ports:
  What the process needs from the outside.
Adapters:
  How the outside world satisfies those needs.
FastAPI:
  One way to drive the application.

Or even simpler:

FastAPI is delivery.
SQLAlchemy is persistence.
Stripe is infrastructure.
The use case is the application.
The domain is the business.

⸻

37. Example: bad vs good

Bad FastAPI endpoint

@router.post("/orders")
async def create_order(
    request: PlaceOrderRequest,
    session: AsyncSession = Depends(get_session),
):
    product_result = await session.execute(
        select(ProductModel).where(ProductModel.id == request.product_id)
    )
    product = product_result.scalar_one()
    if product.stock < request.quantity:
        raise HTTPException(status_code=400, detail="Not enough stock")
    order = OrderModel(
        customer_id=request.customer_id,
        product_id=product.id,
        quantity=request.quantity,
        total=product.price * request.quantity,
    )
    session.add(order)
    product.stock -= request.quantity
    await session.commit()
    await send_email(...)
    return {"id": order.id}

Problems:

HTTP, database, business rules, transaction, and email are all mixed together.
Hard to test without the database.
Hard to reuse outside HTTP.
Hard to change persistence.
Business rule is hidden in the route.

Better FastAPI endpoint

@router.post("/orders", response_model=PlaceOrderResponse)
async def create_order(
    request: PlaceOrderRequest,
    use_case: PlaceOrderUseCase = Depends(get_place_order_use_case),
):
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

Better because:

Endpoint is thin.
Use case owns process.
Domain owns business rules.
Repository owns persistence.
Email adapter owns email.
Transaction is explicit.

⸻

38. Final checklist

A good hexagonal FastAPI app should have these properties:

FastAPI routes are thin.
Business rules live in domain objects or domain services.
Use cases coordinate workflows.
Use cases depend on ports, not concrete adapters.
Repositories hide persistence.
Unit of Work controls transactions.
Pydantic API schemas stay near the API layer.
SQLAlchemy models stay in infrastructure.
Domain has no FastAPI, SQLAlchemy, or cloud SDK imports.
External services are behind ports.
Tests can run use cases with fake adapters.
API tests can override FastAPI dependencies.
Errors are translated at the API boundary.
The folder structure reflects dependency direction, not just naming fashion.

The shortest accurate summary:

A good hexagonal FastAPI app treats FastAPI as an adapter, not as the application.
The business core should be usable without HTTP, without a database, and without the framework.