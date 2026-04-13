from fastapi import FastAPI

from kanban.router import router as kanban_router
from problem_details import register_problem_details

app = FastAPI(
    title="starter-template-fastapi",
    description="FastAPI starter service",
    version="0.1.0",
)

app.include_router(kanban_router)
register_problem_details(app)


@app.get("/")
def read_root() -> dict[str, str]:
    return {
        "name": "starter-template-fastapi",
        "message": "FastAPI service is running.",
    }


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
