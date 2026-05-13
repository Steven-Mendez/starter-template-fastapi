"""Rust-style ``Result`` type used by use cases to signal success or domain failure.

Returning a ``Result`` instead of raising exceptions for expected outcomes
keeps the success and failure branches visible at the type level, makes
exhaustiveness checks easy with structural pattern matching, and lets
HTTP adapters decide how to translate domain errors into responses
without unwinding the stack.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import TypeVar

T = TypeVar("T")
E = TypeVar("E")
U = TypeVar("U")
F = TypeVar("F")


class UnwrapError(RuntimeError):
    """Raised when ``unwrap`` / ``expect`` run on the wrong ``Result`` branch."""


@dataclass(frozen=True, slots=True)
class Ok[T]:
    """Successful ``Result`` carrying the produced value."""

    value: T


@dataclass(frozen=True, slots=True)
class Err[E]:
    """Failed ``Result`` carrying the domain error."""

    error: E


type Result[T, E] = Ok[T] | Err[E]


def is_ok[T, E](result: Result[T, E]) -> bool:
    """Return ``True`` if the ``Result`` is an :class:`Ok` variant."""
    return isinstance(result, Ok)


def is_err[T, E](result: Result[T, E]) -> bool:
    """Return ``True`` if the ``Result`` is an :class:`Err` variant."""
    return isinstance(result, Err)


def unwrap[T, E](result: Result[T, E]) -> T:
    """Return the value or raise :class:`UnwrapError` on :class:`Err`.

    Use only when the caller can statically prove the ``Result`` is
    successful (e.g. immediately after an explicit ``is_ok`` check).
    """
    match result:
        case Ok(value=v):
            return v
        case Err():
            raise UnwrapError("called unwrap on Err")


def unwrap_err[T, E](result: Result[T, E]) -> E:
    """Return the error or raise :class:`UnwrapError` on :class:`Ok`."""
    match result:
        case Err(error=e):
            return e
        case Ok():
            raise UnwrapError("called unwrap_err on Ok")


def expect[T, E](result: Result[T, E], message: str) -> T:
    """Like :func:`unwrap`.

    On :class:`Err`, raises :class:`UnwrapError` including ``message``.
    """
    match result:
        case Ok(value=v):
            return v
        case Err(error=e):
            raise UnwrapError(f"{message}: {e!r}")


def expect_err[T, E](result: Result[T, E], message: str) -> E:
    """Like :func:`unwrap_err`.

    On :class:`Ok`, raises :class:`UnwrapError` including ``message``.
    """
    match result:
        case Err(error=e):
            return e
        case Ok(value=v):
            raise UnwrapError(f"{message}: {v!r}")


def result_map[T, E, U](result: Result[T, E], f: Callable[[T], U]) -> Result[U, E]:
    """Apply ``f`` to the success value, leaving an :class:`Err` untouched."""
    match result:
        case Ok(value=v):
            return Ok(f(v))
        case Err(error=e):
            return Err(e)


def result_map_err[T, E, F](result: Result[T, E], f: Callable[[E], F]) -> Result[T, F]:
    """Apply ``f`` to the error value, leaving an :class:`Ok` untouched."""
    match result:
        case Ok(value=v):
            return Ok(v)
        case Err(error=e):
            return Err(f(e))


def result_and_then[T, E, U](
    result: Result[T, E],
    f: Callable[[T], Result[U, E]],
) -> Result[U, E]:
    """Chain a fallible computation that itself returns a ``Result``.

    Equivalent to Rust's ``Result::and_then``: short-circuits on the
    first :class:`Err` and threads the success value through ``f``.
    """
    match result:
        case Ok(value=v):
            return f(v)
        case Err(error=e):
            return Err(e)


def expect_ok[T, E](result: Result[T, E]) -> T:
    """Return the success value or raise ``AssertionError`` on :class:`Err`.

    Intended for tests where an :class:`Err` always indicates a bug and
    the assertion message should carry the offending error.
    """
    match result:
        case Ok(value=v):
            return v
        case Err(error=e):
            raise AssertionError(e)


def map[T, E, U](result: Result[T, E], f: Callable[[T], U]) -> Result[U, E]:
    """Alias for :func:`result_map` matching the Rust naming."""
    return result_map(result, f)


def map_err[T, E, F](result: Result[T, E], f: Callable[[E], F]) -> Result[T, F]:
    """Alias for :func:`result_map_err` matching the Rust naming."""
    return result_map_err(result, f)


def and_then[T, E, U](
    result: Result[T, E],
    f: Callable[[T], Result[U, E]],
) -> Result[U, E]:
    """Alias for :func:`result_and_then` matching the Rust naming."""
    return result_and_then(result, f)
