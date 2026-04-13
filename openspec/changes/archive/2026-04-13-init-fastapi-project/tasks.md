## 1. Dependencies

- [x] 1.1 Add `fastapi` and `uvicorn[standard]` to `pyproject.toml` dependencies (compatible with `requires-python`).

## 2. Application

- [x] 2.1 Replace placeholder `main.py` with a `FastAPI` instance `app`, `GET /` returning JSON with service identity, and `GET /health` returning JSON liveness.

## 3. Documentation

- [x] 3.1 Update `README.md` with install steps (`uv sync` or `pip install -e .`) and run commands (`uvicorn main:app --reload`, optional `fastapi run main.py`).
