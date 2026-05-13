"""Inbound port protocols for the auth feature.

One protocol per use case; each declares a single execute() method returning
Result so HTTP adapters can use structural pattern matching.
"""

from features.authentication.application.ports.inbound.confirm_email_verification_port import (  # noqa: E501
    ConfirmEmailVerificationPort,
)
from features.authentication.application.ports.inbound.confirm_password_reset_port import (  # noqa: E501
    ConfirmPasswordResetPort,
)
from features.authentication.application.ports.inbound.login_user_port import (
    LoginUserPort,
)
from features.authentication.application.ports.inbound.logout_all_port import (
    LogoutAllPort,
)
from features.authentication.application.ports.inbound.logout_user_port import (
    LogoutUserPort,
)
from features.authentication.application.ports.inbound.refresh_token_port import (
    RefreshTokenPort,
)
from features.authentication.application.ports.inbound.register_user_port import (
    RegisterUserPort,
)
from features.authentication.application.ports.inbound.request_email_verification_port import (  # noqa: E501
    RequestEmailVerificationPort,
)
from features.authentication.application.ports.inbound.request_password_reset_port import (  # noqa: E501
    RequestPasswordResetPort,
)
from features.authentication.application.ports.inbound.resolve_principal_port import (  # noqa: E501
    ResolvePrincipalFromAccessTokenPort,
)

__all__ = [
    "ConfirmEmailVerificationPort",
    "ConfirmPasswordResetPort",
    "LoginUserPort",
    "LogoutAllPort",
    "LogoutUserPort",
    "RefreshTokenPort",
    "RegisterUserPort",
    "RequestEmailVerificationPort",
    "RequestPasswordResetPort",
    "ResolvePrincipalFromAccessTokenPort",
]
