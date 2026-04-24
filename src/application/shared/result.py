from __future__ import annotations

from dataclasses import dataclass
from typing import Generic, TypeVar

T = TypeVar("T")
E = TypeVar("E")


@dataclass(frozen=True, slots=True)
class AppOk(Generic[T]):
    value: T


@dataclass(frozen=True, slots=True)
class AppErr(Generic[E]):
    error: E


type AppResult[T, E] = AppOk[T] | AppErr[E]
