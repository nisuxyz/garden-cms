# middleware/htmx.py
import json
from typing import Optional

from bustapi import Middleware
from bustapi.http.request import Request
from bustapi.http.response import Response


class HTMXDetails:
    """
    Parses all HX-* request headers into typed properties.
    Attached to every request as request.htmx by HTMXMiddleware.
    """
    def __init__(self, request) -> None:
        h = request.headers
        self.is_htmx: bool               = h.get("HX-Request") == "true"
        self.request_type: Optional[str] = h.get("HX-Request-Type")
        self.current_url: Optional[str]  = h.get("HX-Current-URL")
        self.source: Optional[str]       = h.get("HX-Source")
        self.target: Optional[str]       = h.get("HX-Target")
        self.boosted: bool               = h.get("HX-Boosted") == "true"
        self.history_restore: bool       = h.get("HX-History-Restore-Request") == "true"
        self.last_event_id: Optional[str]= h.get("Last-Event-ID")


class HTMXMiddleware(Middleware):
    """Attaches HTMXDetails to request.htmx; adds Vary: HX-Request to all responses."""

    def process_request(self, request: Request) -> None:
        request.htmx = HTMXDetails(request)
        return None

    def process_response(self, request: Request, response: Response) -> Response:
        response.headers["Vary"] = "HX-Request"
        return response


# ── Response helpers ──────────────────────────────────────

def hx_redirect(response: Response, url: str) -> Response:
    """HX-Redirect: client-side redirect with full page reload."""
    response.headers["HX-Redirect"] = url
    return response


def hx_location(response: Response, url: str, **opts) -> Response:
    """HX-Location: AJAX navigation without page reload."""
    response.headers["HX-Location"] = json.dumps({"path": url, **opts}) if opts else url
    return response


def hx_refresh(response: Response) -> Response:
    """HX-Refresh: force full page refresh."""
    response.headers["HX-Refresh"] = "true"
    return response


def hx_push_url(response: Response, url: str) -> Response:
    """HX-Push-Url: push a URL onto the browser history stack."""
    response.headers["HX-Push-Url"] = url
    return response


def hx_replace_url(response: Response, url: str) -> Response:
    """HX-Replace-Url: replace the current browser history entry."""
    response.headers["HX-Replace-Url"] = url
    return response


def hx_trigger(response: Response, event: str, **detail) -> Response:
    """HX-Trigger: fire a client-side event, optionally with a detail payload."""
    response.headers["HX-Trigger"] = json.dumps({event: detail}) if detail else event
    return response
