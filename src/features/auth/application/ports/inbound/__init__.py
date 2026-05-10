"""Inbound port protocols for the auth feature.

One protocol per use case; each declares a single execute() method returning
Result so HTTP adapters can use structural pattern matching.
"""

from src.features.auth.application.ports.inbound.confirm_email_verification_port import (  # noqa: E501
    ConfirmEmailVerificationPort,
)
from src.features.auth.application.ports.inbound.confirm_password_reset_port import (
    ConfirmPasswordResetPort,
)
from src.features.auth.application.ports.inbound.login_user_port import LoginUserPort
from src.features.auth.application.ports.inbound.logout_all_port import LogoutAllPort
from src.features.auth.application.ports.inbound.logout_user_port import LogoutUserPort
from src.features.auth.application.ports.inbound.refresh_token_port import (
    RefreshTokenPort,
)
from src.features.auth.application.ports.inbound.register_user_port import (
    RegisterUserPort,
)
from src.features.auth.application.ports.inbound.request_email_verification_port import (  # noqa: E501
    RequestEmailVerificationPort,
)
from src.features.auth.application.ports.inbound.request_password_reset_port import (
    RequestPasswordResetPort,
)
from src.features.auth.application.ports.inbound.resolve_principal_port import (
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
