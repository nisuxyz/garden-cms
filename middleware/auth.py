# middleware/auth.py
from litestar.connection import ASGIConnection
from litestar.exceptions import NotAuthorizedException
from litestar.handlers import BaseRouteHandler

_LOGIN_PATH = "/admin/login"


def admin_guard(connection: ASGIConnection, _: BaseRouteHandler) -> None:
    """
    Guard for admin routes.
    Raises NotAuthorizedException if the session lacks admin_authenticated.
    The login route itself is excluded by not applying this guard to it.
    """
    if not connection.session.get("admin_authenticated"):
        raise NotAuthorizedException(
            detail="Not authenticated",
            extra={"redirect_to": _LOGIN_PATH},
        )
