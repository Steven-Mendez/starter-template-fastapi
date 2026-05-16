"""Per-feature settings view used by the email composition root.

Holds only the values the feature actually consumes, derived from the
shared :class:`AppSettings`. Keeping a small struct here makes the
``build_email_container`` signature self-documenting and decouples the
adapters from the (much larger) platform settings class.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

EmailBackend = Literal["console", "resend"]


@dataclass(frozen=True, slots=True)
class EmailSettings:
    """Subset of :class:`AppSettings` the email feature reads at startup."""

    backend: EmailBackend
    from_address: str | None
    resend_api_key: str | None
    resend_base_url: str
    # When True AND ``APP_ENVIRONMENT=development``, the console adapter
    # additionally emits the rendered body at INFO. Defaults to False so
    # the body (which may carry single-use reset/verify tokens) never
    # appears in logs by default. Refused outside development.
    console_log_bodies: bool

    @classmethod
    def from_app_settings(
        cls,
        app: Any = None,
        *,
        backend: str | None = None,
        from_address: str | None = None,
        resend_api_key: str | None = None,
        resend_base_url: str | None = None,
        console_log_bodies: bool | None = None,
    ) -> EmailSettings:
        """Construct from either an :class:`AppSettings` or flat kwargs.

        The keyword form is kept for callers that still pass individual
        fields; preferred path is ``EmailSettings.from_app_settings(app)``.
        """
        if app is not None:
            backend = app.email_backend
            from_address = app.email_from
            resend_api_key = app.email_resend_api_key
            resend_base_url = app.email_resend_base_url
            console_log_bodies = app.email_console_log_bodies
        if backend not in ("console", "resend"):
            raise ValueError(
                f"APP_EMAIL_BACKEND must be one of 'console', 'resend'; got {backend!r}"
            )
        return cls(
            backend=backend,  # type: ignore[arg-type]
            from_address=from_address,
            resend_api_key=resend_api_key,
            resend_base_url=resend_base_url or "https://api.resend.com",
            console_log_bodies=bool(console_log_bodies)
            if console_log_bodies is not None
            else False,
        )

    def resolved_from_address(self) -> str:
        """Default sender used when ``APP_EMAIL_FROM`` is unset (console/dev)."""
        return self.from_address or "no-reply@example.com"

    def validate(self, errors: list[str]) -> None:
        """Append always-on (non-production-only) validation errors."""
        if self.backend == "resend":
            missing: list[str] = []
            if not self.resend_api_key:
                missing.append("APP_EMAIL_RESEND_API_KEY")
            if not self.from_address:
                missing.append("APP_EMAIL_FROM")
            if missing:
                errors.append(
                    "APP_EMAIL_BACKEND=resend requires: " + ", ".join(missing)
                )

    def validate_production(self, errors: list[str]) -> None:
        if self.backend == "console":
            errors.append(
                "APP_EMAIL_BACKEND must not be 'console' in production; "
                "configure 'resend' and set the matching credentials"
            )
