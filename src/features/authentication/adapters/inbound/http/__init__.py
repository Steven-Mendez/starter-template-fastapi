"""Auth HTTP adapter package."""

from features.authentication.adapters.inbound.http.cookies import (
    REFRESH_COOKIE_NAME,
    clear_refresh_cookie,
)

__all__ = ["REFRESH_COOKIE_NAME", "clear_refresh_cookie"]
