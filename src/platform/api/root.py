from __future__ import annotations

from fastapi import APIRouter

root_router = APIRouter(tags=["root"])


@root_router.get("/")
def read_root() -> dict[str, str]:
    return {
        "name": "starter-template-fastapi",
        "message": "FastAPI service is running.",
    }
