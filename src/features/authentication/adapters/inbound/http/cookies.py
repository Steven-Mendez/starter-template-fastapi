"""Refresh-token cookie helpers.

Exposes :func:`clear_refresh_cookie` as a public helper so non-authentication
features (e.g. ``users.DELETE /me``) can invalidate the browser-side refresh
cookie at the source. The cookie attributes (path, secure, samesite) must
match the original ``Set-Cookie`` exactly or browsers may treat the delete
as targeting a different cookie and leave the original in place.
"""

from __future__ import annotations

from fastapi import Request, Response

from features.authentication.composition.app_state import get_auth_container

REFRESH_COOKIE_NAME = "refresh_token"


def clear_refresh_cookie(response: Response, request: Request) -> None:
    """Instruct the browser to delete the refresh-token cookie.

    Attributes must match the original ``Set-Cookie`` exactly (path, secure,
    samesite) or some browsers will treat the delete as targeting a different
    cookie and leave the original in place.
    """
    settings = get_auth_container(request).settings
    response.delete_cookie(
        key=REFRESH_COOKIE_NAME,
        path="/auth",
        secure=settings.auth_cookie_secure,
        samesite=settings.auth_cookie_samesite,
    )
