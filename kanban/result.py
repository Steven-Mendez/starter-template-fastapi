from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Generic, TypeVar

T = TypeVar("T")
T_co = TypeVar("T_co", covariant=True)
E = TypeVar("E")
U = TypeVar("U")
F = TypeVar("F")


class UnwrapError(RuntimeError):
    """Raised when unwrap/expect is used on the wrong Result variant."""


@dataclass(frozen=True, slots=True)
class Ok(Generic[T_co]):
    value: T_co


@dataclass(frozen=True, slots=True)
class Err(Generic[E]):
    error: E


type Result[T, E] = Ok[T] | Err[E]


def is_ok(result: Result[T, E]) -> bool:
    return isinstance(result, Ok)


def is_err(result: Result[T, E]) -> bool:
    return isinstance(result, Err)


def unwrap(result: Result[T, E]) -> T:
    match result:
        case Ok(value=v):
            return v
        case Err():
            raise UnwrapError("called unwrap on Err")


def unwrap_err(result: Result[T, E]) -> E:
    match result:
        case Err(error=e):
            return e
        case Ok():
            raise UnwrapError("called unwrap_err on Ok")


def expect(result: Result[T, E], message: str) -> T:
    match result:
        case Ok(value=v):
            return v
        case Err(error=e):
            raise UnwrapError(f"{message}: {e!r}")


def expect_err(result: Result[T, E], message: str) -> E:
    match result:
        case Err(error=e):
            return e
        case Ok(value=v):
            raise UnwrapError(f"{message}: {v!r}")


def result_map(result: Result[T, E], f: Callable[[T], U]) -> Result[U, E]:
    match result:
        case Ok(value=v):
            return Ok(f(v))
        case Err(error=e):
            return Err(e)


def result_map_err(result: Result[T, E], f: Callable[[E], F]) -> Result[T, F]:
    match result:
        case Ok(value=v):
            return Ok(v)
        case Err(error=e):
            return Err(f(e))


def result_and_then(
    result: Result[T, E],
    f: Callable[[T], Result[U, E]],
) -> Result[U, E]:
    match result:
        case Ok(value=v):
            return f(v)
        case Err(error=e):
            return Err(e)


def expect_ok(result: Result[T, E]) -> T:
    match result:
        case Ok(value=v):
            return v
        case Err(error=e):
            raise AssertionError(e)


def map(result: Result[T, E], f: Callable[[T], U]) -> Result[U, E]:
    return result_map(result, f)


def map_err(result: Result[T, E], f: Callable[[E], F]) -> Result[T, F]:
    return result_map_err(result, f)


def and_then(
    result: Result[T, E],
    f: Callable[[T], Result[U, E]],
) -> Result[U, E]:
    return result_and_then(result, f)
