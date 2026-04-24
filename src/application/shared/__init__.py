"""Shared application contracts and abstractions."""

from src.application.shared.errors import ApplicationError, from_domain_error
from src.application.shared.result import AppErr, AppOk, AppResult
from src.application.shared.unit_of_work import UnitOfWork

__all__ = [
    "AppErr",
    "AppOk",
    "AppResult",
    "ApplicationError",
    "UnitOfWork",
    "from_domain_error",
]
