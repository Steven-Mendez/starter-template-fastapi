"""Runtime registry of email templates contributed by features.

Mirrors the authorization registry pattern: each feature that sends
email calls :meth:`register_template` at composition time. The registry
is sealed in ``main.py`` before the application serves traffic, after
which further registration attempts raise.

A template entry pairs a *subject* template (a short Jinja2 string)
with a *body* template (the path to a Jinja2 file on disk). The
registry renders both with the supplied context.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from jinja2 import (
    Environment,
    FileSystemLoader,
    StrictUndefined,
    Template,
    TemplateError,
    select_autoescape,
)

from features.email.application.errors import (
    TemplateRenderError,
    UnknownTemplateError,
)
from features.email.domain.message import RenderedEmail


@dataclass(frozen=True, slots=True)
class _Entry:
    """One registered template: subject (inline) + body (file)."""

    subject: str
    body_path: Path


@dataclass(slots=True)
class EmailTemplateRegistry:
    """Mutable registry of email templates owned by the email feature.

    Features register their templates by calling
    :meth:`register_template`; the composition root seals the registry
    after every feature has contributed. The registry refuses to render
    a template it does not know about — surfacing the typo as an
    :class:`UnknownTemplateError` at the call site rather than as a
    silently dropped email.
    """

    _entries: dict[str, _Entry] = field(default_factory=dict)
    _sealed: bool = False
    _search_paths: list[Path] = field(default_factory=list)

    def register_template(
        self,
        name: str,
        *,
        subject: str,
        body_path: str | Path,
    ) -> None:
        """Register a template under ``name``.

        ``subject`` is a small Jinja2 string rendered inline. ``body_path``
        points at a Jinja2 template file on disk. The directory containing
        the file is added to the registry's Jinja2 search path so
        ``{% extends %}`` and ``{% include %}`` work without further
        configuration.
        """
        self._guard_unsealed()
        if name in self._entries:
            raise ValueError(f"Email template {name!r} is already registered")
        path = Path(body_path)
        if not path.exists():
            raise FileNotFoundError(
                f"Template file {path!s} for {name!r} does not exist"
            )
        self._entries[name] = _Entry(subject=subject, body_path=path)
        parent = path.parent
        if parent not in self._search_paths:
            self._search_paths.append(parent)

    def seal(self) -> None:
        """Freeze the registry; further registrations raise ``RuntimeError``."""
        self._sealed = True

    def registered_templates(self) -> set[str]:
        """Return the set of template names known to the registry."""
        return set(self._entries)

    def has(self, name: str) -> bool:
        """Return whether ``name`` was registered."""
        return name in self._entries

    def render(
        self,
        *,
        to: str,
        template_name: str,
        context: dict[str, Any],
    ) -> RenderedEmail:
        """Render a registered template into a :class:`RenderedEmail`.

        Raises:
            UnknownTemplateError: ``template_name`` was never registered.
            TemplateRenderError: Jinja2 raised during rendering (most
                often a missing variable, since ``StrictUndefined`` is
                enabled — that is intentional to catch payload typos at
                the boundary).
        """
        entry = self._entries.get(template_name)
        if entry is None:
            raise UnknownTemplateError(template_name=template_name)

        environment = self._environment()
        try:
            subject_template: Template = environment.from_string(entry.subject)
            body_template = environment.get_template(entry.body_path.name)
            subject_text = subject_template.render(**context).strip()
            body_text = body_template.render(**context)
        except TemplateError as exc:
            raise TemplateRenderError(
                template_name=template_name, reason=str(exc)
            ) from exc

        return RenderedEmail(to=to, subject=subject_text, body=body_text)

    def _environment(self) -> Environment:
        """Construct a fresh Jinja2 environment over the registered paths."""
        return Environment(
            loader=FileSystemLoader([str(p) for p in self._search_paths]),
            autoescape=select_autoescape(
                enabled_extensions=("html", "htm", "xml"),
                default_for_string=False,
            ),
            undefined=StrictUndefined,
            keep_trailing_newline=True,
        )

    def _guard_unsealed(self) -> None:
        if self._sealed:
            raise RuntimeError(
                "EmailTemplateRegistry is sealed; register all templates "
                "before composition completes"
            )
