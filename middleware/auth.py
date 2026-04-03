# middleware/auth.py
from bustapi import Middleware
from bustapi.http.request import Request
from bustapi.http.response import Response

_LOGIN_PATH = "/admin/login"


class AdminAuthMiddleware(Middleware):
    """
    Guards all /admin/* routes except /admin/login.
    Reads admin_authenticated from request.session.
    Redirects unauthenticated requests to /admin/login.
    """

    def process_request(self, request: Request) -> Response | None:
        if not request.path.startswith("/admin"):
            return None
        if request.path == _LOGIN_PATH:
            return None
        session = getattr(request, "session", None)
        if session and session.get("admin_authenticated"):
            return None
        resp = Response("", status=302)
        resp.headers["Location"] = _LOGIN_PATH
        return resp

    def process_response(self, request: Request, response: Response) -> Response:
        return response
