from __future__ import annotations

import pytest

from kanban.result import (
    Err,
    Ok,
    UnwrapError,
    expect,
    is_err,
    is_ok,
    result_and_then,
    result_map,
    result_map_err,
    unwrap,
    unwrap_err,
)

pytestmark = pytest.mark.unit


def test_unwrap_returns_value() -> None:
    assert unwrap(Ok(7)) == 7


def test_unwrap_raises_on_err() -> None:
    with pytest.raises(UnwrapError):
        unwrap(Err("bad"))


def test_expect_returns_value() -> None:
    assert expect(Ok(7), "nope") == 7


def test_expect_raises_on_err() -> None:
    with pytest.raises(UnwrapError):
        expect(Err("bad"), "nope")


def test_is_ok_is_err() -> None:
    assert is_ok(Ok(1)) and not is_err(Ok(1))
    assert is_err(Err(2)) and not is_ok(Err(2))


def test_result_map_applies_on_ok() -> None:
    r: Ok[int] | Err[str] = result_map(Ok(2), lambda x: x * 3)
    assert unwrap(r) == 6


def test_result_map_passes_through_err() -> None:
    r: Ok[int] | Err[str] = result_map(Err("e"), lambda x: x)
    assert unwrap_err(r) == "e"


def test_result_map_err_transforms_error() -> None:
    r: Ok[int] | Err[str] = result_map_err(Err(1), lambda n: f"err-{n}")
    assert unwrap_err(r) == "err-1"


def test_result_and_then_chains_ok() -> None:
    r: Ok[int] | Err[str] = result_and_then(Ok(2), lambda x: Ok(x + 1))
    assert unwrap(r) == 3


def test_result_and_then_short_circuits_on_err() -> None:
    r: Ok[str] | Err[str] = result_and_then(Err("a"), lambda x: Ok(x))
    assert unwrap_err(r) == "a"
