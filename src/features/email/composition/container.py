"""Composition root for the email feature.

Builds the :class:`EmailTemplateRegistry`, selects the active adapter
based on :class:`EmailSettings.backend`, and returns an
:class:`EmailContainer` that exposes both — the registry so other
features can contribute templates during composition, and the adapter
(behind :class:`EmailPort`) so consumers can send mail.
"""

from __future__ import annotations

from dataclasses import dataclass

from src.features.email.adapters.outbound.console import ConsoleEmailAdapter
from src.features.email.adapters.outbound.resend import ResendEmailAdapter
from src.features.email.adapters.outbound.smtp import SmtpEmailAdapter
from src.features.email.application.ports.email_port import EmailPort
from src.features.email.application.registry import EmailTemplateRegistry
from src.features.email.composition.settings import EmailSettings


@dataclass(slots=True)
class EmailContainer:
    """Bundle of the registry and the wired :class:`EmailPort` adapter."""

    settings: EmailSettings
    registry: EmailTemplateRegistry
    port: EmailPort


def build_email_container(settings: EmailSettings) -> EmailContainer:
    """Build the email feature's container.

    The registry is created empty; consumer features (e.g.
    ``authentication``) register their templates during their own
    composition phase. The composition root calls ``registry.seal()``
    once every feature has run.
    """
    registry = EmailTemplateRegistry()

    port: EmailPort
    if settings.backend == "console":
        port = ConsoleEmailAdapter(registry=registry)
    elif settings.backend == "smtp":
        if settings.smtp_host is None:
            raise RuntimeError(
                "APP_EMAIL_SMTP_HOST is required when APP_EMAIL_BACKEND=smtp"
            )
        port = SmtpEmailAdapter(
            registry=registry,
            host=settings.smtp_host,
            port=settings.smtp_port,
            from_address=settings.resolved_from_address(),
            username=settings.smtp_username,
            password=settings.smtp_password,
            use_starttls=settings.smtp_use_starttls,
            use_ssl=settings.smtp_use_ssl,
            timeout=settings.smtp_timeout_seconds,
        )
    elif settings.backend == "resend":
        if not settings.resend_api_key:
            raise RuntimeError(
                "APP_EMAIL_RESEND_API_KEY is required when APP_EMAIL_BACKEND=resend"
            )
        port = ResendEmailAdapter(
            registry=registry,
            api_key=settings.resend_api_key,
            from_address=settings.resolved_from_address(),
            base_url=settings.resend_base_url,
        )
    else:  # pragma: no cover - guarded by EmailSettings construction
        raise RuntimeError(f"Unknown email backend: {settings.backend!r}")

    return EmailContainer(settings=settings, registry=registry, port=port)
