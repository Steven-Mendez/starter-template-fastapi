"""Composition root for the email feature.

Builds the :class:`EmailTemplateRegistry`, selects the active adapter
based on :class:`EmailSettings.backend`, and returns an
:class:`EmailContainer` that exposes both — the registry so other
features can contribute templates during composition, and the adapter
(behind :class:`EmailPort`) so consumers can send mail.
"""

from __future__ import annotations

from dataclasses import dataclass

from features.email.adapters.outbound.console import ConsoleEmailAdapter
from features.email.application.ports.email_port import EmailPort
from features.email.application.registry import EmailTemplateRegistry
from features.email.composition.settings import EmailSettings


@dataclass(slots=True)
class EmailContainer:
    """Bundle of the registry and the wired :class:`EmailPort` adapter."""

    settings: EmailSettings
    registry: EmailTemplateRegistry
    port: EmailPort


def build_email_container(
    settings: EmailSettings, *, environment: str = "development"
) -> EmailContainer:
    """Build the email feature's container.

    The registry is created empty; consumer features (e.g.
    ``authentication``) register their templates during their own
    composition phase. The composition root calls ``registry.seal()``
    once every feature has run.

    ``environment`` is read from ``AppSettings.environment`` and
    forwarded to the console adapter so the opt-in full-body log line
    only fires in development. Other backends ignore it.
    """
    registry = EmailTemplateRegistry()

    port: EmailPort
    if settings.backend == "console":
        port = ConsoleEmailAdapter(
            registry=registry,
            log_bodies=settings.console_log_bodies,
            environment=environment,
        )
    else:  # pragma: no cover - guarded by EmailSettings construction
        raise RuntimeError(f"Unknown email backend: {settings.backend!r}")

    return EmailContainer(settings=settings, registry=registry, port=port)
