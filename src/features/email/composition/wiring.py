"""Wiring helpers for the email feature."""

from __future__ import annotations

from typing import cast

from fastapi import FastAPI

from features.email.composition.container import EmailContainer


def attach_email_container(app: FastAPI, container: EmailContainer) -> None:
    """Publish the :class:`EmailContainer` on ``app.state``."""
    app.state.email_container = container


def get_email_container(app: FastAPI) -> EmailContainer:
    """Return the previously-attached :class:`EmailContainer`."""
    container = getattr(app.state, "email_container", None)
    if container is None:
        raise RuntimeError("EmailContainer has not been attached to app.state")
    return cast(EmailContainer, container)
