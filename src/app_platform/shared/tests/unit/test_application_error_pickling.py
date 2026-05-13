"""Pickle round-trip contract for every concrete ``ApplicationError`` subclass.

arq dispatches jobs through Redis and pickles any exception raised inside a
handler. ``Exception.__reduce__`` only round-trips positional ``args``;
subclasses that need additional state MUST implement ``__reduce__`` returning
``(cls, (positional_args,))``. This test walks every leaf subclass of
``ApplicationError`` and asserts the round-trip preserves both type and
``str()``. Bases that exist only to anchor a feature hierarchy are excluded.
"""

from __future__ import annotations

import dataclasses
import importlib
import inspect
import pickle
import sys
from collections.abc import Iterable
from typing import Any

import pytest

# Importing the package modules registers every feature subclass with
# ``ApplicationError.__subclasses__()``.
_FEATURE_ERROR_MODULES = (
    "app_platform.shared.errors",
    "features.authentication.application.errors",
    "features.authorization.application.errors",
    "features.email.application.errors",
    "features.background_jobs.application.errors",
    "features.outbox.application.errors",
    "features.file_storage.application.errors",
    "features.users.application.errors",
)

for _module in _FEATURE_ERROR_MODULES:
    importlib.import_module(_module)

from app_platform.shared.errors import ApplicationError  # noqa: E402

# Per-feature abstract base classes. They are real concrete classes but they
# exist only to group their subclasses; do not exercise them directly.
_FEATURE_BASES = {
    "AuthError",
    "AuthorizationError",
    "EmailError",
    "JobError",
    "OutboxError",
    "FileStorageError",
    "UserError",
}


def _all_subclasses(cls: type) -> Iterable[type]:
    seen: set[type] = set()

    def walk(node: type) -> Iterable[type]:
        for sub in node.__subclasses__():
            if sub in seen:
                continue
            seen.add(sub)
            yield sub
            yield from walk(sub)

    yield from walk(cls)


def _is_canonical(cls: type) -> bool:
    """Return True if ``cls`` is the binding currently exposed by its module.

    ``@dataclass(slots=True)`` builds a brand-new class object and rebinds the
    module-level name to it; the original (pre-decorator) class object stays
    in ``cls.__subclasses__()`` because it's still reachable. Filter those
    shadows out — only the class accessible via ``getattr(module, qualname)``
    matches what ``pickle`` will look up on the receiving side.
    """
    module = sys.modules.get(cls.__module__)
    if module is None:  # pragma: no cover - defensive
        return False
    obj: object = module
    for part in cls.__qualname__.split("."):
        obj = getattr(obj, part, None)
        if obj is None:
            return False
    return obj is cls


_TYPE_SAMPLES: dict[type, Any] = {
    str: "test message",
    int: 1,
    float: 1.0,
    bool: True,
    bytes: b"test",
}


def _sample_for_field_type(field_type: Any) -> Any:
    """Pick a sample value for a dataclass field's declared type.

    Field types may be raw types or stringified annotations (PEP 563). Fall
    back to a string sample for anything unrecognized — a concrete pickle
    failure signals the class needs a custom ``__reduce__``.
    """
    if isinstance(field_type, type):
        return _TYPE_SAMPLES.get(field_type, "test")
    return "test"


def _build_positional_args(error_cls: type[ApplicationError]) -> tuple[Any, ...]:
    """Return positional arguments suitable for constructing ``error_cls``.

    Dataclass-shaped errors expose typed fields; other subclasses follow the
    plain ``Exception(message)`` shape. Annotations the helper does not
    recognize fall back to a string sample so the round-trip still exercises
    something — a concrete failure here means the class needs a custom
    ``__reduce__``.
    """
    if dataclasses.is_dataclass(error_cls):
        return tuple(
            _sample_for_field_type(field.type)
            for field in dataclasses.fields(error_cls)
        )
    # Pure Exception subclass — use the conventional single-message shape unless
    # the __init__ signature accepts no args (e.g. a no-arg sentinel error).
    try:
        sig = inspect.signature(error_cls)
    except (TypeError, ValueError):
        return ("test message",)
    required = [
        p
        for p in sig.parameters.values()
        if p.default is inspect.Parameter.empty
        and p.kind
        in (
            inspect.Parameter.POSITIONAL_ONLY,
            inspect.Parameter.POSITIONAL_OR_KEYWORD,
        )
    ]
    if not required:
        return ()
    return tuple("test message" for _ in required)


def _concrete_subclasses() -> list[type[ApplicationError]]:
    return [
        cls
        for cls in _all_subclasses(ApplicationError)
        if cls.__name__ not in _FEATURE_BASES and _is_canonical(cls)
    ]


@pytest.mark.unit
@pytest.mark.parametrize(
    "error_cls",
    _concrete_subclasses(),
    ids=lambda cls: cls.__name__,
)
def test_application_error_pickles_round_trip(
    error_cls: type[ApplicationError],
) -> None:
    """Every concrete ``ApplicationError`` subclass round-trips through pickle.

    The default ``Exception.__init__(*args)`` shape is used. If a subclass
    requires kwargs, implement ``__reduce__`` returning ``(cls, (positional,))``
    so this contract test continues to pass.
    """
    try:
        args = _build_positional_args(error_cls)
        instance = error_cls(*args)
    except TypeError as exc:  # pragma: no cover - surfaces broken signatures
        pytest.fail(
            f"{error_cls.__name__} cannot be constructed positionally: "
            f"{exc!s}. Implement __reduce__ returning "
            f"(cls, (positional_args,)) to keep pickle working."
        )

    loaded = pickle.loads(pickle.dumps(instance))

    assert type(loaded) is error_cls
    assert str(loaded) == str(instance)
