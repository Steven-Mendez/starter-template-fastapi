from fastapi import FastAPI

app = FastAPI(
    title="starter-template-fastapi",
    description="FastAPI starter service",
    version="0.1.0",
)


@app.get("/")
def read_root() -> dict[str, str]:
    return {
        "name": "starter-template-fastapi",
        "message": "FastAPI service is running.",
    }


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
