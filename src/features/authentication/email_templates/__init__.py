"""Email templates owned by the authentication feature.

Registered with the email feature's :class:`EmailTemplateRegistry` at
composition time so the email feature has no static knowledge of which
features send mail; instead each feature contributes its own templates.

Template names are namespaced (``authentication/...``) to make
collisions impossible across features that register independently.
"""

from __future__ import annotations

from pathlib import Path

from features.email.application.registry import EmailTemplateRegistry

_TEMPLATES_DIR = Path(__file__).resolve().parent

PASSWORD_RESET_TEMPLATE = "authentication/password_reset"  # noqa: S105 — template name, not a credential
VERIFY_EMAIL_TEMPLATE = "authentication/verify_email"


def register_authentication_email_templates(registry: EmailTemplateRegistry) -> None:
    """Register password-reset and verify-email templates on ``registry``."""
    registry.register_template(
        PASSWORD_RESET_TEMPLATE,
        subject="Reset your {{ app_name }} password",
        body_path=_TEMPLATES_DIR / "password_reset.txt",
    )
    registry.register_template(
        VERIFY_EMAIL_TEMPLATE,
        subject="Verify your {{ app_name }} email",
        body_path=_TEMPLATES_DIR / "verify_email.txt",
    )
