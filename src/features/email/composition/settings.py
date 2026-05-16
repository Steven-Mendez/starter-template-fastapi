"""Per-feature settings view used by the email composition root.

Holds only the values the feature actually consumes, derived from the
shared :class:`AppSettings`. Keeping a small struct here makes the
``build_email_container`` signature self-documenting and decouples the
adapters from the (much larger) platform settings class.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

EmailBackend = Literal["console"]


@dataclass(frozen=True, slots=True)
class EmailSettings:
    """Subset of :class:`AppSettings` the email feature reads at startup."""

    backend: EmailBackend
    from_address: str | None
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
        console_log_bodies: bool | None = None,
    ) -> EmailSettings:
        """Construct from either an :class:`AppSettings` or flat kwargs.

        The keyword form is kept for callers that still pass individual
        fields; preferred path is ``EmailSettings.from_app_settings(app)``.
        """
        if app is not None:
            backend = app.email_backend
            from_address = app.email_from
            console_log_bodies = app.email_console_log_bodies
        if backend not in ("console",):
            # Deliberately does not echo the rejected value: the only
            # accepted backend is ``'console'`` and the message must not
            # name a removed backend (``resend``/``smtp``) as if it were
            # an option (see the email capability spec).
            raise ValueError(
                "APP_EMAIL_BACKEND must be 'console' (the only accepted "
                "email backend); the supplied value is not recognised"
            )
        return cls(
            backend=backend,  # type: ignore[arg-type]
            from_address=from_address,
            console_log_bodies=bool(console_log_bodies)
            if console_log_bodies is not None
            else False,
        )

    def validate(self, errors: list[str]) -> None:
        """Append always-on (non-production-only) validation errors."""

    def validate_production(self, errors: list[str]) -> None:
        if self.backend == "console":
            errors.append(
                "APP_EMAIL_BACKEND must not be 'console' in production; "
                "no production-capable email backend exists yet "
                "(AWS SES arrives at a later roadmap step)"
            )
