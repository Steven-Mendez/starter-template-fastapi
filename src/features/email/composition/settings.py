"""Per-feature settings view used by the email composition root.

Holds only the values the feature actually consumes, derived from the
shared :class:`AppSettings`. Keeping a small struct here makes the
``build_email_container`` signature self-documenting and decouples the
adapters from the (much larger) platform settings class.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

EmailBackend = Literal["console", "smtp", "resend"]


@dataclass(frozen=True, slots=True)
class EmailSettings:
    """Subset of :class:`AppSettings` the email feature reads at startup."""

    backend: EmailBackend
    from_address: str | None
    smtp_host: str | None
    smtp_port: int
    smtp_username: str | None
    smtp_password: str | None
    smtp_use_starttls: bool
    smtp_use_ssl: bool
    smtp_timeout_seconds: float
    resend_api_key: str | None
    resend_base_url: str

    @classmethod
    def from_app_settings(
        cls,
        app: Any = None,
        *,
        backend: str | None = None,
        from_address: str | None = None,
        smtp_host: str | None = None,
        smtp_port: int | None = None,
        smtp_username: str | None = None,
        smtp_password: str | None = None,
        smtp_use_starttls: bool | None = None,
        smtp_use_ssl: bool | None = None,
        smtp_timeout_seconds: float | None = None,
        resend_api_key: str | None = None,
        resend_base_url: str | None = None,
    ) -> "EmailSettings":
        """Construct from either an :class:`AppSettings` or flat kwargs.

        The keyword form is kept for callers that still pass individual
        fields; preferred path is ``EmailSettings.from_app_settings(app)``.
        """
        if app is not None:
            backend = app.email_backend
            from_address = app.email_from
            smtp_host = app.email_smtp_host
            smtp_port = app.email_smtp_port
            smtp_username = app.email_smtp_username
            smtp_password = app.email_smtp_password
            smtp_use_starttls = app.email_smtp_use_starttls
            smtp_use_ssl = app.email_smtp_use_ssl
            smtp_timeout_seconds = app.email_smtp_timeout_seconds
            resend_api_key = app.email_resend_api_key
            resend_base_url = app.email_resend_base_url
        if backend not in ("console", "smtp", "resend"):
            raise ValueError(
                "APP_EMAIL_BACKEND must be one of 'console', 'smtp', 'resend'; "
                f"got {backend!r}"
            )
        return cls(
            backend=backend,  # type: ignore[arg-type]
            from_address=from_address,
            smtp_host=smtp_host,
            smtp_port=smtp_port if smtp_port is not None else 587,
            smtp_username=smtp_username,
            smtp_password=smtp_password,
            smtp_use_starttls=(
                True if smtp_use_starttls is None else smtp_use_starttls
            ),
            smtp_use_ssl=False if smtp_use_ssl is None else smtp_use_ssl,
            smtp_timeout_seconds=(
                10.0 if smtp_timeout_seconds is None else smtp_timeout_seconds
            ),
            resend_api_key=resend_api_key,
            resend_base_url=resend_base_url or "https://api.resend.com",
        )

    def resolved_from_address(self) -> str:
        """Default sender used when ``APP_EMAIL_FROM`` is unset (console/dev)."""
        return self.from_address or "no-reply@example.com"

    def validate(self, errors: list[str]) -> None:
        """Append always-on (non-production-only) validation errors."""
        if self.backend == "smtp":
            missing: list[str] = []
            if not self.smtp_host:
                missing.append("APP_EMAIL_SMTP_HOST")
            if not self.from_address:
                missing.append("APP_EMAIL_FROM")
            if self.smtp_port <= 0:
                missing.append("APP_EMAIL_SMTP_PORT")
            if missing:
                errors.append("APP_EMAIL_BACKEND=smtp requires: " + ", ".join(missing))
        if self.backend == "resend":
            missing = []
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
                "configure 'smtp' or 'resend' and set the matching credentials"
            )
