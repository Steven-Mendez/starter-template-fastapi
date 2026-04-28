"""Live server fixtures for e2e tests."""

from __future__ import annotations

import os
import socket
import subprocess
import time
from collections.abc import Generator
from contextlib import contextmanager
from pathlib import Path

import httpx
import pytest
from alembic.config import Config
from docker.errors import DockerException  # type: ignore[import-untyped]
from testcontainers.postgres import PostgresContainer  # type: ignore[import-untyped]

from alembic import command

REPO_ROOT = Path(__file__).resolve().parents[2]


def _unused_tcp_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return int(s.getsockname()[1])


@pytest.fixture(scope="module")
def api_base_url() -> Generator[str, None, None]:
    port = _unused_tcp_port()
    try:
        with PostgresContainer("postgres:16-alpine") as postgres:
            dsn = _normalize_postgres_dsn(postgres.get_connection_url())
            _run_migrations(dsn)

            env = os.environ.copy()
            env["APP_POSTGRESQL_DSN"] = dsn
            proc = subprocess.Popen(
                [
                    "uv",
                    "run",
                    "uvicorn",
                    "main:app",
                    "--host",
                    "127.0.0.1",
                    "--port",
                    str(port),
                ],
                cwd=REPO_ROOT,
                env=env,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )

            base = f"http://127.0.0.1:{port}"
            deadline = time.time() + 20.0
            last_err: Exception | None = None
            try:
                while time.time() < deadline:
                    if proc.poll() is not None:
                        raise RuntimeError(
                            "uvicorn exited before accepting connections"
                        )
                    try:
                        response = httpx.get(f"{base}/health", timeout=1.0)
                        if response.status_code == 200:
                            break
                    except Exception as exc:
                        last_err = exc
                        time.sleep(0.05)
                else:
                    raise RuntimeError(f"server did not become ready: {last_err!r}")
                yield base
            finally:
                proc.terminate()
                try:
                    proc.wait(timeout=15)
                except subprocess.TimeoutExpired:
                    proc.kill()
                    proc.wait(timeout=5)
    except DockerException as exc:
        pytest.skip(f"Docker is required for PostgreSQL e2e tests: {exc}")


def _normalize_postgres_dsn(raw_dsn: str) -> str:
    if raw_dsn.startswith("postgresql+psycopg2://"):
        return raw_dsn.replace("postgresql+psycopg2://", "postgresql+psycopg://", 1)
    if raw_dsn.startswith("postgresql://"):
        return raw_dsn.replace("postgresql://", "postgresql+psycopg://", 1)
    return raw_dsn


def _run_migrations(database_url: str) -> None:
    with _temporary_env_var("APP_POSTGRESQL_DSN", database_url):
        command.upgrade(Config("alembic.ini"), "head")


@contextmanager
def _temporary_env_var(name: str, value: str) -> Generator[None, None, None]:
    previous = os.environ.get(name)
    os.environ[name] = value
    try:
        yield
    finally:
        if previous is None:
            os.environ.pop(name, None)
        else:
            os.environ[name] = previous
