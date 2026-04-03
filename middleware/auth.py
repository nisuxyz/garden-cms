# middleware/auth.py
from litestar.connection import ASGIConnection
from litestar.exceptions import NotAuthorizedException
from litestar.handlers import BaseRouteHandler

_LOGIN_PATH = "/admin/login"


def admin_guard(connection: ASGIConnection, _: BaseRouteHandler) -> None:
    """
    Guard for admin routes.

    Checks the Litestar session cookie for ``admin_authenticated``.
    This works for both the legacy ADMIN_PASSWORD flow *and* the
    Piccolo BaseUser flow — both set the same session flag on login.
    """
    if not connection.session.get("admin_authenticated"):
        raise NotAuthorizedException(
            detail="Not authenticated",
            extra={"redirect_to": _LOGIN_PATH},
        )
