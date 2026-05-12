"""HTTP router for the template feature.

Routes are gated by ``require_authorization`` so the application layer
never sees an unauthorized request. The router translates application
``Result`` values to HTTP responses; HTTP-level details (status codes,
schemas, headers) never leak into the use cases.
"""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, HTTPException, Request, status

from src.features._template.adapters.inbound.http.dependencies import (
    get_template_container,
)
from src.features._template.adapters.inbound.http.schemas import (
    CreateThingRequest,
    ListThingsResponse,
    ThingResponse,
    UpdateThingRequest,
)
from src.features._template.application.errors import ApplicationError
from src.features._template.application.use_cases.create_thing import (
    CreateThingCommand,
)
from src.features._template.application.use_cases.delete_thing import (
    DeleteThingCommand,
)
from src.features._template.application.use_cases.get_thing import GetThingQuery
from src.features._template.application.use_cases.list_things import ListThingsQuery
from src.features._template.application.use_cases.update_thing import (
    UpdateThingCommand,
)
from src.features._template.domain.models.thing import Thing
from src.platform.api.authorization import (
    CurrentPrincipalDep,
    require_authorization,
)
from src.platform.shared.result import Err, Ok


def _to_response(thing: Thing) -> ThingResponse:
    return ThingResponse(
        id=thing.id,
        name=thing.name,
        owner_id=thing.owner_id,
        created_at=thing.created_at,
        updated_at=thing.updated_at,
    )


def _id_from_path(request: Request) -> str:
    return request.path_params["thing_id"]


def _map_error(error: ApplicationError) -> HTTPException:
    if error is ApplicationError.NOT_FOUND:
        # 403 (not 404) so the API does not reveal resource existence to
        # unauthorized callers. Authorized callers reach this branch only
        # when the resource genuinely does not exist, in which case 403
        # is acceptable consistency.
        return HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Permission denied",
        )
    if error is ApplicationError.NAME_REQUIRED:
        return HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="name must be a non-empty string",
        )
    return HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail="Unexpected error",
    )


def build_template_router() -> APIRouter:
    router = APIRouter()

    @router.post(
        "",
        response_model=ThingResponse,
        status_code=status.HTTP_201_CREATED,
    )
    def create_thing(
        request: Request,
        body: CreateThingRequest,
        principal: CurrentPrincipalDep,
    ) -> ThingResponse:
        container = get_template_container(request.app)
        result = container.create_thing().execute(
            CreateThingCommand(name=body.name, owner_id=principal.user_id)
        )
        match result:
            case Ok(value=thing):
                return _to_response(thing)
            case Err(error=err):
                raise _map_error(err)

    @router.get("", response_model=ListThingsResponse)
    def list_things(
        request: Request,
        principal: CurrentPrincipalDep,
    ) -> ListThingsResponse:
        container = get_template_container(request.app)
        things = container.list_things().execute(
            ListThingsQuery(user_id=principal.user_id)
        )
        return ListThingsResponse(items=[_to_response(t) for t in things])

    @router.get(
        "/{thing_id}",
        response_model=ThingResponse,
        dependencies=[require_authorization("read", "thing", _id_from_path)],
    )
    def get_thing(request: Request, thing_id: UUID) -> ThingResponse:
        container = get_template_container(request.app)
        result = container.get_thing().execute(GetThingQuery(thing_id=thing_id))
        match result:
            case Ok(value=thing):
                return _to_response(thing)
            case Err(error=err):
                raise _map_error(err)

    @router.patch(
        "/{thing_id}",
        response_model=ThingResponse,
        dependencies=[require_authorization("update", "thing", _id_from_path)],
    )
    def update_thing(
        request: Request,
        thing_id: UUID,
        body: UpdateThingRequest,
    ) -> ThingResponse:
        container = get_template_container(request.app)
        result = container.update_thing().execute(
            UpdateThingCommand(thing_id=thing_id, new_name=body.name)
        )
        match result:
            case Ok(value=thing):
                return _to_response(thing)
            case Err(error=err):
                raise _map_error(err)

    @router.delete(
        "/{thing_id}",
        status_code=status.HTTP_204_NO_CONTENT,
        dependencies=[require_authorization("delete", "thing", _id_from_path)],
    )
    def delete_thing(request: Request, thing_id: UUID) -> None:
        container = get_template_container(request.app)
        result = container.delete_thing().execute(DeleteThingCommand(thing_id=thing_id))
        match result:
            case Ok():
                return None
            case Err(error=err):
                raise _map_error(err)

    return router
