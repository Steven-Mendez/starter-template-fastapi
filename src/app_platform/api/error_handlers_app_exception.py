"""HTTPException subclass carrying metadata for Problem Details responses."""

from __future__ import annotations

from fastapi import HTTPException


class ApplicationHTTPException(HTTPException):
    """Carrier for application-layer errors mapped to HTTP with Problem+JSON metadata.

    Features raise subclasses or instances of this exception from their inbound
    HTTP adapters. The generic platform handler renders the payload as RFC 9457
    Problem Details using the ``code`` and ``type_uri`` attributes.
    """

    def __init__(
        self,
        *,
        status_code: int,
        detail: str,
        code: str,
        type_uri: str,
        headers: dict[str, str] | None = None,
    ) -> None:
        """Build an exception for Problem+JSON with ``code`` and ``type_uri``.

        ``headers`` is forwarded to the underlying :class:`HTTPException` so the
        platform exception handler can copy them onto the outgoing Problem+JSON
        response (e.g. ``WWW-Authenticate: Bearer`` on 401, ``Retry-After: N``
        on 429).
        """
        super().__init__(status_code=status_code, detail=detail, headers=headers)
        self.code = code
        self.type_uri = type_uri
