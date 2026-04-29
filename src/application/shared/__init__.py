"""Shared application contracts and abstractions."""

from src.application.shared.readiness import ReadinessProbe
from src.domain.shared.result import Err, Ok, Result

__all__ = ["Err", "Ok", "ReadinessProbe", "Result"]
