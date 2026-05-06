"""HTTPException subclass carrying metadata for Problem Details responses."""

from __future__ import annotations

from fastapi import HTTPException


class ApplicationHTTPException(HTTPException):
    """Carrier for application-layer errors mapped to HTTP with Problem+JSON metadata.

    Features (e.g. kanban) raise subclasses or instances of this exception from
    their inbound HTTP adapters. The generic platform handler renders the payload
    as RFC 9457 Problem Details using the ``code`` and ``type_uri`` attributes.
    """

    def __init__(
        self,
        *,
        status_code: int,
        detail: str,
        code: str,
        type_uri: str,
    ) -> None:
        """Build an exception for Problem+JSON with ``code`` and ``type_uri``."""
        super().__init__(status_code=status_code, detail=detail)
        self.code = code
        self.type_uri = type_uri
