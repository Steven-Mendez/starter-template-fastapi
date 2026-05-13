"""Unit tests for :class:`EmailTemplateRegistry` rendering and lifecycle."""

from __future__ import annotations

from pathlib import Path

import pytest

from features.email.application.errors import (
    TemplateRenderError,
    UnknownTemplateError,
)
from features.email.application.registry import EmailTemplateRegistry

pytestmark = pytest.mark.unit


def _write(tmp_path: Path, name: str, body: str) -> Path:
    path = tmp_path / name
    path.write_text(body)
    return path


def test_registers_and_renders_template(tmp_path: Path) -> None:
    body_path = _write(tmp_path, "welcome.txt", "Hi {{ name }}!\n")
    registry = EmailTemplateRegistry()
    registry.register_template(
        "test/welcome", subject="Hello {{ name }}", body_path=body_path
    )

    message = registry.render(
        to="alice@example.com",
        template_name="test/welcome",
        context={"name": "Alice"},
    )

    assert message.to == "alice@example.com"
    assert message.subject == "Hello Alice"
    assert message.body == "Hi Alice!\n"


def test_unknown_template_raises(tmp_path: Path) -> None:
    registry = EmailTemplateRegistry()
    with pytest.raises(UnknownTemplateError):
        registry.render(
            to="alice@example.com",
            template_name="never-registered",
            context={},
        )


def test_missing_context_variable_raises_render_error(tmp_path: Path) -> None:
    body_path = _write(tmp_path, "broken.txt", "Hi {{ name }}!\n")
    registry = EmailTemplateRegistry()
    registry.register_template("t/broken", subject="s", body_path=body_path)

    with pytest.raises(TemplateRenderError):
        registry.render(to="x@example.com", template_name="t/broken", context={})


def test_seal_blocks_further_registration(tmp_path: Path) -> None:
    body_path = _write(tmp_path, "a.txt", "body")
    registry = EmailTemplateRegistry()
    registry.register_template("a", subject="s", body_path=body_path)
    registry.seal()

    with pytest.raises(RuntimeError, match="sealed"):
        registry.register_template("b", subject="s", body_path=body_path)


def test_duplicate_registration_raises(tmp_path: Path) -> None:
    body_path = _write(tmp_path, "a.txt", "body")
    registry = EmailTemplateRegistry()
    registry.register_template("a", subject="s", body_path=body_path)
    with pytest.raises(ValueError, match="already registered"):
        registry.register_template("a", subject="s", body_path=body_path)


def test_missing_template_file_raises(tmp_path: Path) -> None:
    registry = EmailTemplateRegistry()
    with pytest.raises(FileNotFoundError):
        registry.register_template(
            "a", subject="s", body_path=tmp_path / "does-not-exist.txt"
        )


def test_registered_templates_lists_names(tmp_path: Path) -> None:
    body_path = _write(tmp_path, "a.txt", "body")
    registry = EmailTemplateRegistry()
    registry.register_template("a", subject="s", body_path=body_path)
    registry.register_template("b", subject="s", body_path=body_path)

    assert registry.registered_templates() == {"a", "b"}
    assert registry.has("a")
    assert not registry.has("c")
