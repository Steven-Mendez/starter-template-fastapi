"""Domain model for a rendered email ready to be dispatched."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class RenderedEmail:
    """A fully rendered transactional email.

    Adapters consume this struct; they are free to add ``From``, ``Date``
    and other transport headers. The body is always plain text — HTML
    templates can be added in a follow-up without touching the port.
    """

    to: str
    subject: str
    body: str
