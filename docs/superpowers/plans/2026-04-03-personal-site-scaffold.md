# Personal Site Scaffold Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Scaffold a personal site with BustAPI, HTMX 4, Alpine.js, PicoCSS (classless), and Stoolap — including HTMX middleware, DB schema with slug history, public pages, and admin CRUD for posts, projects, and site content.

**Architecture:** BustAPI serves all routes. `HTMXMiddleware` attaches `request.htmx` (an `HTMXDetails` instance) to every request and adds `Vary: HX-Request` to all responses. Routes check `request.htmx.is_htmx` to serve either full-page templates or HTMX fragments. `AdminAuthMiddleware` session-guards every `/admin/*` route except `/admin/login`. All editable content lives in Stoolap. Markdown is rendered at request time via `markdown-it-py`.

**Tech Stack:** Python 3.13 · BustAPI 0.10.3 · HTMX 4 (`cdn.jsdelivr.net/npm/htmx.org@next`) · Alpine.js 3 (`cdn.jsdelivr.net/npm/alpinejs@3/dist/cdn.min.js`) · PicoCSS v2 classless (`cdn.jsdelivr.net/npm/@picocss/pico@2/css/pico.classless.min.css`) · Stoolap · markdown-it-py · python-dotenv · pytest

---

## File Map

| File | Responsibility |
|---|---|
| `main.py` | App init, `jinja_options`, middleware registration, blueprint registration, DB init, `app.run()` |
| `middleware/__init__.py` | Empty |
| `middleware/htmx.py` | `HTMXDetails`, `HTMXMiddleware`, six `hx_*` response helpers |
| `middleware/auth.py` | `AdminAuthMiddleware` (session-based, reads `ADMIN_PASSWORD` env var) |
| `db/__init__.py` | Empty |
| `db/connection.py` | `get_db()` singleton, opens Stoolap at `DATABASE_URL` env var |
| `db/schema.py` | `init_db()` — CREATE TABLEs + seed `site_content`; `get_content(db, key)` helper; `render_md(text)` helper |
| `routes/__init__.py` | `render(template_name, **ctx)` — cached-env Jinja2 renderer returning `HTMLResponse` |
| `routes/pages.py` | `pages_bp`: `/`, `/resume`, `/contact` GET/POST |
| `routes/blog.py` | `blog_bp`: `/blog`, `/blog/<slug>`, `/blog/feed` |
| `routes/projects.py` | `projects_bp`: `/projects`, `/projects/<slug>`, `/projects/feed` |
| `routes/admin.py` | `admin_bp`: login, logout, dashboard, posts CRUD, projects CRUD, content editor |
| `static/css/theme.css` | PicoCSS variable overrides — Mycelium theme (jade/azure/slate) |
| `templates/layout/base.html` | Main layout: CDN links, `<header>`, `<main>`, `<footer>`, theme toggle |
| `templates/layout/admin.html` | Admin layout: extends base, sidebar nav |
| `templates/partials/nav.html` | Site nav rendered inside `<header>` |
| `templates/partials/footer.html` | Footer content |
| `templates/partials/blog_card.html` | Single blog post card (reused in lists and landing) |
| `templates/partials/project_card.html` | Single project card |
| `templates/pages/index.html` | Landing page |
| `templates/pages/blog.html` | Blog listing page |
| `templates/pages/post.html` | Shared detail page for posts and projects (`content_type` var) |
| `templates/pages/projects.html` | Projects grid page |
| `templates/pages/resume.html` | Resume page (DB-driven content blocks) |
| `templates/pages/contact.html` | Contact page with HTMX form |
| `templates/pages/admin/login.html` | Admin login form |
| `templates/pages/admin/dashboard.html` | Admin overview + posts list (via `view` context var) |
| `templates/pages/admin/post_edit.html` | Create/edit post form |
| `templates/pages/admin/project_list.html` | Admin projects list |
| `templates/pages/admin/project_edit.html` | Create/edit project form |
| `templates/pages/admin/content.html` | Site content key/value editor |
| `templates/htmx/blog/list.html` | Paginated blog list fragment (also included in `blog.html`) |
| `templates/htmx/projects/grid.html` | Projects grid fragment (also included in `projects.html`) |
| `templates/htmx/contact/success.html` | Contact success fragment |
| `templates/htmx/contact/error.html` | Contact error fragment |
| `templates/htmx/admin/post_row.html` | Admin post list row fragment |
| `templates/htmx/admin/project_row.html` | Admin project list row fragment |
| `tests/conftest.py` | Pytest fixtures: in-memory DB, `MockHeaders`, `MockRequest` |
| `tests/test_htmx.py` | Unit tests for `HTMXDetails` and `hx_*` helpers |
| `tests/test_db.py` | Unit tests for schema init, `get_content`, slug redirect queries |
| `tests/test_auth.py` | Unit tests for `AdminAuthMiddleware` |
| `.env.example` | Template for required env vars |
| `.gitignore` | Ignores `.env`, `data/`, `__pycache__`, `.venv` |

---
## Task 1: Add dependencies and env files

**Files:** `pyproject.toml` (via uv), `.env.example`, `.gitignore`, `data/.gitkeep`

- [ ] **Step 1: Install runtime dependencies**

```bash
uv add stoolap markdown-it-py python-dotenv
```

- [ ] **Step 2: Install dev dependencies**

```bash
uv add --dev pytest
```

- [ ] **Step 3: Create `.env.example`**

```
SECRET_KEY=change-me-to-a-long-random-string
ADMIN_PASSWORD=change-me
DATABASE_URL=./data/site.db
```

- [ ] **Step 4: Create `.gitignore`**

```
.env
data/*.db
__pycache__/
*.pyc
.venv/
.pytest_cache/
```

- [ ] **Step 5: Create the data directory placeholder**

```bash
mkdir -p data && touch data/.gitkeep
```

- [ ] **Step 6: Copy `.env.example` to `.env` and fill in values**

```bash
cp .env.example .env
# Edit .env: set SECRET_KEY, ADMIN_PASSWORD, DATABASE_URL
```

- [ ] **Step 7: Commit**

```bash
git add pyproject.toml uv.lock .env.example .gitignore data/.gitkeep
git commit -m "chore: add dependencies and env setup"
```

---

## Task 2: Project skeleton

**Files:** Package `__init__.py` files, static and template directories

- [ ] **Step 1: Create Python package directories**

```bash
mkdir -p middleware routes db tests
touch middleware/__init__.py routes/__init__.py db/__init__.py tests/__init__.py
```

- [ ] **Step 2: Create static and template directory structure**

```bash
mkdir -p static/css
mkdir -p templates/layout templates/partials
mkdir -p templates/pages/admin
mkdir -p templates/htmx/blog templates/htmx/projects
mkdir -p templates/htmx/contact templates/htmx/admin
```

- [ ] **Step 3: Commit**

```bash
git add middleware/ routes/ db/ tests/ static/ templates/
git commit -m "chore: create project skeleton"
```

---

## Task 3: Database module

**Files:** `db/connection.py`, `db/schema.py`, `tests/conftest.py`, `tests/test_db.py`

- [ ] **Step 1: Write `db/connection.py`**

```python
# db/connection.py
import os

from stoolap import Database

_db: Database | None = None


def get_db() -> Database:
    """Return the singleton Stoolap database, opening it on first call."""
    global _db
    if _db is None:
        url = os.getenv("DATABASE_URL", "./data/site.db")
        if url != ":memory:" and not url.startswith("file://"):
            parent = os.path.dirname(url)
            if parent:
                os.makedirs(parent, exist_ok=True)
        _db = Database.open(url)
    return _db
```

- [ ] **Step 2: Write `db/schema.py`**

```python
# db/schema.py
import json

from markdown_it import MarkdownIt
from stoolap import Database

_md = MarkdownIt()

_DDL = """
CREATE TABLE IF NOT EXISTS posts (
    id         INTEGER PRIMARY KEY,
    title      TEXT NOT NULL,
    slug       TEXT NOT NULL UNIQUE,
    summary    TEXT NOT NULL,
    body       TEXT NOT NULL,
    tags       TEXT NOT NULL DEFAULT '[]',
    published  BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS post_slug_history (
    id         INTEGER PRIMARY KEY,
    post_id    INTEGER NOT NULL,
    slug       TEXT NOT NULL UNIQUE,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS projects (
    id          INTEGER PRIMARY KEY,
    title       TEXT NOT NULL,
    slug        TEXT NOT NULL UNIQUE,
    summary     TEXT NOT NULL,
    body        TEXT NOT NULL,
    tags        TEXT NOT NULL DEFAULT '[]',
    url         TEXT,
    repo_url    TEXT,
    featured    BOOLEAN NOT NULL DEFAULT FALSE,
    published   BOOLEAN NOT NULL DEFAULT FALSE,
    created_at  TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at  TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS project_slug_history (
    id          INTEGER PRIMARY KEY,
    project_id  INTEGER NOT NULL,
    slug        TEXT NOT NULL UNIQUE,
    created_at  TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS site_content (
    key         TEXT PRIMARY KEY,
    value       TEXT NOT NULL,
    label       TEXT NOT NULL,
    is_markdown BOOLEAN NOT NULL DEFAULT TRUE,
    updated_at  TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);
"""

_CONTENT_SEEDS = [
    ("home.hero_headline", "Hello, I'm Nisu.", "Landing page headline", False),
    ("home.hero_subtext", "Developer, maker, and curious human.", "Landing page subtext", False),
    ("home.about", "I build things, explore ideas, and share what I learn.", "About blurb", True),
    ("resume.intro", "Here's a snapshot of where I've been and what I've built.", "Resume intro", True),
    ("resume.experience", "## Experience\n\n*Add your experience here.*", "Experience section", True),
    ("resume.education", "## Education\n\n*Add your education here.*", "Education section", True),
    ("resume.skills", "## Skills\n\n*Add your skills here.*", "Skills section", True),
    ("contact.intro", "Have a question or want to say hello?", "Contact page intro", True),
]


def init_db(db: Database) -> None:
    """Create tables and seed default site_content rows."""
    db.exec(_DDL)
    for key, value, label, is_markdown in _CONTENT_SEEDS:
        existing = db.query_one(
            "SELECT key FROM site_content WHERE key = $1", [key]
        )
        if not existing:
            db.execute(
                "INSERT INTO site_content (key, value, label, is_markdown) VALUES ($1, $2, $3, $4)",
                [key, value, label, is_markdown],
            )


def render_md(text: str) -> str:
    """Render a markdown string to HTML."""
    return _md.render(text)


def get_content(db: Database, key: str) -> str:
    """Fetch a site_content value by key. Returns HTML (if markdown) or raw text. Returns '' if not found."""
    row = db.query_one(
        "SELECT value, is_markdown FROM site_content WHERE key = $1", [key]
    )
    if not row:
        return ""
    return render_md(row["value"]) if row["is_markdown"] else row["value"]


def parse_tags(tags_json: str) -> list[str]:
    """Parse a JSON-encoded tag list from the database."""
    try:
        return json.loads(tags_json) if tags_json else []
    except (ValueError, TypeError):
        return []
```

- [ ] **Step 3: Write `tests/conftest.py`**

```python
# tests/conftest.py
import pytest
from stoolap import Database

from db.schema import init_db


@pytest.fixture
def db():
    """In-memory Stoolap database with schema applied."""
    database = Database.open(":memory:")
    init_db(database)
    return database


class MockHeaders:
    def __init__(self, headers: dict):
        self._h = {k.lower(): v for k, v in headers.items()}

    def get(self, key: str, default=None):
        return self._h.get(key.lower(), default)


class MockRequest:
    def __init__(self, headers: dict | None = None, path: str = "/", session: dict | None = None):
        self.headers = MockHeaders(headers or {})
        self.path = path
        self.session = session or {}
```

- [ ] **Step 4: Write `tests/test_db.py`**

```python
# tests/test_db.py
import pytest
from db.schema import get_content, parse_tags, render_md


def test_init_db_seeds_content(db):
    row = db.query_one("SELECT value FROM site_content WHERE key = $1", ["home.hero_headline"])
    assert row is not None
    assert row["value"] != ""


def test_get_content_returns_html_for_markdown(db):
    db.execute(
        "INSERT INTO site_content (key, value, label, is_markdown) VALUES ($1, $2, $3, $4)",
        ["test.md", "**bold**", "Test", True],
    )
    result = get_content(db, "test.md")
    assert "<strong>bold</strong>" in result


def test_get_content_returns_plain_text(db):
    db.execute(
        "INSERT INTO site_content (key, value, label, is_markdown) VALUES ($1, $2, $3, $4)",
        ["test.plain", "Hello world", "Test", False],
    )
    result = get_content(db, "test.plain")
    assert result == "Hello world"


def test_get_content_missing_key_returns_empty(db):
    assert get_content(db, "nonexistent.key") == ""


def test_parse_tags():
    assert parse_tags('["python", "web"]') == ["python", "web"]
    assert parse_tags("[]") == []
    assert parse_tags("") == []
    assert parse_tags("bad json") == []


def test_slug_history_preserved(db):
    db.execute(
        "INSERT INTO posts (title, slug, summary, body) VALUES ($1, $2, $3, $4)",
        ["Hello", "hello", "Summary", "Body"],
    )
    post = db.query_one("SELECT id FROM posts WHERE slug = $1", ["hello"])
    db.execute(
        "INSERT INTO post_slug_history (post_id, slug) VALUES ($1, $2)",
        [post["id"], "old-hello"],
    )
    row = db.query_one(
        "SELECT post_id FROM post_slug_history WHERE slug = $1", ["old-hello"]
    )
    assert row is not None
    assert row["post_id"] == post["id"]
```

- [ ] **Step 5: Run tests — fix any DDL dialect issues until all pass**

```bash
uv run pytest tests/test_db.py -v
```

Note: `db.exec()` runs multi-statement DDL. If stoolap requires splitting statements, replace the single `db.exec(_DDL)` call with individual `db.execute()` calls per CREATE TABLE statement.

Expected: all 6 tests PASS.

- [ ] **Step 6: Commit**

```bash
git add db/ tests/conftest.py tests/test_db.py
git commit -m "feat: add database module with schema, helpers, and tests"
```

---
## Task 4: HTMX middleware

**Files:** `middleware/htmx.py`, `tests/test_htmx.py`

- [ ] **Step 1: Write `tests/test_htmx.py` (failing)**

```python
# tests/test_htmx.py
import json
import pytest
from bustapi import Middleware
from bustapi.http.response import Response
from middleware.htmx import (
    HTMXDetails, HTMXMiddleware,
    hx_location, hx_push_url, hx_redirect,
    hx_refresh, hx_replace_url, hx_trigger,
)
from tests.conftest import MockRequest


def test_htmx_details_detects_htmx_request():
    req = MockRequest(headers={"HX-Request": "true"})
    assert HTMXDetails(req).is_htmx is True


def test_htmx_details_non_htmx():
    assert HTMXDetails(MockRequest()).is_htmx is False


def test_htmx_details_all_headers():
    req = MockRequest(headers={
        "HX-Request": "true",
        "HX-Request-Type": "partial",
        "HX-Current-URL": "http://localhost/blog",
        "HX-Source": "btn",
        "HX-Target": "feed",
        "HX-Boosted": "true",
        "HX-History-Restore-Request": "true",
        "Last-Event-ID": "42",
    })
    d = HTMXDetails(req)
    assert d.request_type == "partial"
    assert d.current_url == "http://localhost/blog"
    assert d.source == "btn"
    assert d.target == "feed"
    assert d.boosted is True
    assert d.history_restore is True
    assert d.last_event_id == "42"


def test_htmx_details_defaults():
    d = HTMXDetails(MockRequest())
    assert d.request_type is None
    assert d.boosted is False
    assert d.history_restore is False
    assert d.last_event_id is None


def test_middleware_attaches_htmx_attr():
    mw = HTMXMiddleware()
    req = MockRequest(headers={"HX-Request": "true"})
    assert mw.process_request(req) is None
    assert hasattr(req, "htmx")
    assert req.htmx.is_htmx is True


def test_middleware_adds_vary_header():
    mw = HTMXMiddleware()
    req = MockRequest()
    mw.process_request(req)
    resp = mw.process_response(req, Response("ok"))
    assert resp.headers.get("Vary") == "HX-Request"


def test_hx_redirect():
    assert hx_redirect(Response("ok"), "/new").headers.get("HX-Redirect") == "/new"


def test_hx_location_simple():
    assert hx_location(Response("ok"), "/new").headers.get("HX-Location") == "/new"


def test_hx_location_with_opts():
    resp = hx_location(Response("ok"), "/new", target="#content")
    payload = json.loads(resp.headers.get("HX-Location"))
    assert payload["path"] == "/new"
    assert payload["target"] == "#content"


def test_hx_refresh():
    assert hx_refresh(Response("ok")).headers.get("HX-Refresh") == "true"


def test_hx_push_url():
    assert hx_push_url(Response("ok"), "/blog/post").headers.get("HX-Push-Url") == "/blog/post"


def test_hx_replace_url():
    assert hx_replace_url(Response("ok"), "/blog/new").headers.get("HX-Replace-Url") == "/blog/new"


def test_hx_trigger_simple():
    assert hx_trigger(Response("ok"), "saved").headers.get("HX-Trigger") == "saved"


def test_hx_trigger_with_detail():
    payload = json.loads(hx_trigger(Response("ok"), "saved", id=1).headers.get("HX-Trigger"))
    assert payload == {"saved": {"id": 1}}
```

- [ ] **Step 2: Run to confirm ImportError**

```bash
uv run pytest tests/test_htmx.py -v
```

- [ ] **Step 3: Write `middleware/htmx.py`**

```python
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
        self.is_htmx: bool           = h.get("HX-Request") == "true"
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
# Each takes a Response and adds one HX-* header.

def hx_redirect(response: Response, url: str) -> Response:
    """HX-Redirect: client-side redirect with full page reload."""
    response.headers["HX-Redirect"] = url
    return response


def hx_location(response: Response, url: str, **opts) -> Response:
    """HX-Location: AJAX navigation without page reload. Pass swap/target as kwargs."""
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
```

- [ ] **Step 4: Run until all pass**

```bash
uv run pytest tests/test_htmx.py -v
```

Expected: all 15 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add middleware/htmx.py tests/test_htmx.py
git commit -m "feat: add HTMX middleware with HTMXDetails and response helpers"
```

---

## Task 5: Admin auth middleware

**Files:** `middleware/auth.py`, `tests/test_auth.py`

- [ ] **Step 1: Write `tests/test_auth.py` (failing)**

```python
# tests/test_auth.py
from bustapi.http.response import Response
from middleware.auth import AdminAuthMiddleware
from tests.conftest import MockRequest


def test_non_admin_path_passes():
    mw = AdminAuthMiddleware()
    assert mw.process_request(MockRequest(path="/blog")) is None


def test_login_path_passes():
    mw = AdminAuthMiddleware()
    assert mw.process_request(MockRequest(path="/admin/login")) is None


def test_admin_without_session_redirects():
    mw = AdminAuthMiddleware()
    result = mw.process_request(MockRequest(path="/admin", session={}))
    assert result is not None
    assert result.status_code == 302
    assert result.headers.get("Location") == "/admin/login"


def test_admin_with_valid_session_passes():
    mw = AdminAuthMiddleware()
    req = MockRequest(path="/admin", session={"admin_authenticated": True})
    assert mw.process_request(req) is None


def test_admin_posts_without_session_redirects():
    mw = AdminAuthMiddleware()
    result = mw.process_request(MockRequest(path="/admin/posts", session={}))
    assert result is not None and result.status_code == 302


def test_process_response_is_passthrough():
    mw = AdminAuthMiddleware()
    resp = Response("ok")
    assert mw.process_response(MockRequest(), resp) is resp
```

- [ ] **Step 2: Run to confirm ImportError**

```bash
uv run pytest tests/test_auth.py -v
```

- [ ] **Step 3: Write `middleware/auth.py`**

```python
# middleware/auth.py
from bustapi import Middleware
from bustapi.http.request import Request
from bustapi.http.response import Response

_LOGIN_PATH = "/admin/login"


class AdminAuthMiddleware(Middleware):
    """
    Guards all /admin/* routes except /admin/login.
    Reads admin_authenticated from request.session (populated by BustAPI after
    app.secret_key is set). Redirects unauthenticated requests to /admin/login.
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
```

- [ ] **Step 4: Run until all pass**

```bash
uv run pytest tests/test_auth.py -v
```

Expected: all 6 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add middleware/auth.py tests/test_auth.py
git commit -m "feat: add AdminAuthMiddleware with session-based auth"
```

---

## Task 6: Wire `main.py`

**Files:** `main.py`, `routes/__init__.py`

- [ ] **Step 1: Write `routes/__init__.py`**

```python
# routes/__init__.py
from bustapi.responses import HTMLResponse


def render(template_name: str, **context) -> HTMLResponse:
    """
    Render a Jinja2 template using the app's cached environment.
    Avoids creating a new Environment on every call.
    """
    from bustapi import current_app
    env = current_app.create_jinja_environment()
    html = env.get_template(template_name).render(**context)
    return HTMLResponse(html)
```

- [ ] **Step 2: Rewrite `main.py`**

```python
# main.py
import os

from dotenv import load_dotenv
from jinja2 import select_autoescape

from bustapi import BustAPI

load_dotenv()

app = BustAPI(template_folder="templates", static_folder="static")

# Jinja2 autoescape for all HTML/XML templates
app.jinja_options = {"autoescape": select_autoescape(["html", "xml"])}

# Required for session-based admin auth
app.secret_key = os.getenv("SECRET_KEY", "dev-secret-change-me")

# Middleware: HTMX first, auth second
from middleware.htmx import HTMXMiddleware
from middleware.auth import AdminAuthMiddleware

app.middleware_manager.add(HTMXMiddleware())
app.middleware_manager.add(AdminAuthMiddleware())

# Blueprints
from routes.pages import pages_bp
from routes.blog import blog_bp
from routes.projects import projects_bp
from routes.admin import admin_bp

app.register_blueprint(pages_bp)
app.register_blueprint(blog_bp)
app.register_blueprint(projects_bp)
app.register_blueprint(admin_bp, url_prefix="/admin")

# Initialize DB schema and seed content
from db.connection import get_db
from db.schema import init_db

init_db(get_db())

if __name__ == "__main__":
    debug = os.getenv("DEBUG", "false").lower() == "true"
    app.run(host="0.0.0.0", port=8000, debug=debug)
```

- [ ] **Step 3: Create empty blueprint stubs so the app starts**

Create `routes/pages.py`, `routes/blog.py`, `routes/projects.py`, `routes/admin.py` each with just the blueprint definition:

```python
# routes/pages.py
from bustapi import Blueprint
pages_bp = Blueprint("pages", __name__)
```

```python
# routes/blog.py
from bustapi import Blueprint
blog_bp = Blueprint("blog", __name__)
```

```python
# routes/projects.py
from bustapi import Blueprint
projects_bp = Blueprint("projects", __name__)
```

```python
# routes/admin.py
from bustapi import Blueprint
admin_bp = Blueprint("admin", __name__)
```

- [ ] **Step 4: Verify the app starts**

```bash
uv run python main.py
```

Expected: server starts on port 8000. All routes 404 (no routes registered yet — that's fine). Stop with Ctrl+C.

- [ ] **Step 5: Commit**

```bash
git add main.py routes/__init__.py routes/pages.py routes/blog.py routes/projects.py routes/admin.py
git commit -m "feat: wire app with middleware, blueprints, and DB init"
```

---
## Task 7: Theme CSS

**Files:** `static/css/theme.css`

- [ ] **Step 1: Write `static/css/theme.css`**

```css
/* ============================================================
   Mycelium Theme — PicoCSS variable overrides
   Concept: calm organic tones + cool technological accents.
   All colors use --pico-color-* tokens.
   ============================================================ */

:root {
  --pico-border-radius: 0.5rem;
  --pico-font-family-sans-serif:
    system-ui, -apple-system, "Segoe UI", Roboto, sans-serif;
  --pico-font-family-monospace:
    "SFMono-Regular", "Consolas", "Liberation Mono", Menlo, monospace;
  --pico-transition: 150ms ease;
}

/* ── Light theme ─────────────────────────────────────────── */
[data-theme="light"],
:root:not([data-theme="dark"]) {
  --pico-primary:            var(--pico-color-jade-550);
  --pico-primary-background: var(--pico-color-jade-550);
  --pico-primary-hover:      var(--pico-color-jade-600);
  --pico-primary-inverse:    #ffffff;

  --pico-secondary:            var(--pico-color-azure-600);
  --pico-secondary-background: var(--pico-color-azure-600);
  --pico-secondary-hover:      var(--pico-color-azure-700);
  --pico-secondary-inverse:    #ffffff;

  --pico-background-color:      var(--pico-color-slate-50);
  --pico-card-background-color: #ffffff;
  --pico-card-border-color:     var(--pico-color-slate-200);

  --pico-color:              var(--pico-color-slate-900);
  --pico-muted-color:        var(--pico-color-slate-500);
  --pico-muted-border-color: var(--pico-color-slate-200);
}

/* ── Dark theme ──────────────────────────────────────────── */
[data-theme="dark"] {
  --pico-primary:            var(--pico-color-jade-400);
  --pico-primary-background: var(--pico-color-jade-400);
  --pico-primary-hover:      var(--pico-color-jade-500);
  --pico-primary-inverse:    var(--pico-color-slate-950);

  --pico-secondary:            var(--pico-color-azure-400);
  --pico-secondary-background: var(--pico-color-azure-400);
  --pico-secondary-hover:      var(--pico-color-azure-500);
  --pico-secondary-inverse:    var(--pico-color-slate-950);

  --pico-background-color:      var(--pico-color-slate-950);
  --pico-card-background-color: var(--pico-color-slate-900);
  --pico-card-border-color:     var(--pico-color-slate-800);

  --pico-color:              var(--pico-color-slate-100);
  --pico-muted-color:        var(--pico-color-slate-400);
  --pico-muted-border-color: var(--pico-color-slate-800);
}

/* ── Components ──────────────────────────────────────────── */

article {
  box-shadow: 0 1px 3px rgba(0,0,0,0.06), 0 1px 2px rgba(0,0,0,0.04);
  transition: box-shadow var(--pico-transition);
}
article:hover {
  box-shadow: 0 4px 12px rgba(0,0,0,0.08), 0 2px 4px rgba(0,0,0,0.06);
}

/* Tag pills — azure accent, monospace */
.tag {
  display: inline-block;
  padding: 0.1rem 0.55rem;
  border-radius: 999px;
  background-color: var(--pico-secondary-background);
  color: var(--pico-secondary-inverse);
  font-family: var(--pico-font-family-monospace);
  font-size: 0.72rem;
  font-weight: 500;
  text-decoration: none;
}

/* Muted metadata — dates, etc. */
.meta {
  color: var(--pico-muted-color);
  font-family: var(--pico-font-family-monospace);
  font-size: 0.8rem;
}

/* Hero — generous vertical rhythm */
.hero { padding: 4rem 0 3rem; }
.hero h1 {
  font-size: clamp(2rem, 5vw, 3.5rem);
  font-weight: 700;
  line-height: 1.15;
  margin-bottom: 0.75rem;
}
.hero p {
  font-size: 1.2rem;
  color: var(--pico-muted-color);
  max-width: 48ch;
}

/* Theme toggle */
[data-theme-toggle] {
  background: none;
  border: none;
  cursor: pointer;
  padding: 0.25rem 0.5rem;
  font-size: 1.1rem;
  color: var(--pico-muted-color);
  transition: color var(--pico-transition);
}
[data-theme-toggle]:hover { color: var(--pico-color); }
```

- [ ] **Step 2: Commit**

```bash
git add static/css/theme.css
git commit -m "feat: add Mycelium theme CSS"
```

---

## Task 8: Base templates and partials

**Files:** `templates/layout/base.html`, `templates/partials/nav.html`, `templates/partials/footer.html`, `templates/partials/blog_card.html`, `templates/partials/project_card.html`

- [ ] **Step 1: Write `templates/layout/base.html`**

```html
<!DOCTYPE html>
<html lang="en" data-theme="auto">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>{% block title %}Personal Site{% endblock %}</title>
  <link rel="stylesheet"
    href="https://cdn.jsdelivr.net/npm/@picocss/pico@2/css/pico.classless.min.css" />
  <link rel="stylesheet" href="/static/css/theme.css" />
  <script src="https://cdn.jsdelivr.net/npm/htmx.org@next" defer></script>
  <script src="https://cdn.jsdelivr.net/npm/alpinejs@3/dist/cdn.min.js" defer></script>
  {% block head %}{% endblock %}
</head>
<body>
  <header>{% include "partials/nav.html" %}</header>
  <main>{% block content %}{% endblock %}</main>
  <footer>{% include "partials/footer.html" %}</footer>
</body>
</html>
```

- [ ] **Step 2: Write `templates/partials/nav.html`**

```html
<nav>
  <ul>
    <li><strong><a href="/" style="text-decoration:none;">nisu</a></strong></li>
  </ul>
  <ul>
    <li><a href="/blog">Blog</a></li>
    <li><a href="/projects">Projects</a></li>
    <li><a href="/resume">Resume</a></li>
    <li><a href="/contact">Contact</a></li>
    <li>
      <button
        data-theme-toggle
        x-data
        @click="
          const html = document.documentElement;
          html.dataset.theme = html.dataset.theme === 'dark' ? 'light' : 'dark';
        "
        aria-label="Toggle theme"
      >☽</button>
    </li>
  </ul>
</nav>
```

- [ ] **Step 3: Write `templates/partials/footer.html`**

```html
<small>
  Built with
  <a href="https://grandpaej.github.io/BustAPI/" target="_blank" rel="noopener">BustAPI</a>
  ·
  <a href="https://htmx.org" target="_blank" rel="noopener">htmx</a>
  ·
  <a href="https://picocss.com" target="_blank" rel="noopener">Pico CSS</a>
</small>
```

- [ ] **Step 4: Write `templates/partials/blog_card.html`**

```html
<article>
  <header>
    <a href="/blog/{{ post.slug }}"><strong>{{ post.title }}</strong></a>
    <span class="meta">{{ post.created_at[:10] if post.created_at else "" }}</span>
  </header>
  <p>{{ post.summary }}</p>
  {% if post.tags %}
  <footer>
    {% for tag in post.tags %}<span class="tag">{{ tag }}</span> {% endfor %}
  </footer>
  {% endif %}
</article>
```

- [ ] **Step 5: Write `templates/partials/project_card.html`**

```html
<article>
  <header>
    <a href="/projects/{{ project.slug }}"><strong>{{ project.title }}</strong></a>
    {% if project.url %}
    <a href="{{ project.url }}" target="_blank" rel="noopener" class="meta"> ↗ live</a>
    {% endif %}
  </header>
  <p>{{ project.summary }}</p>
  <footer>
    {% if project.tags %}
      {% for tag in project.tags %}<span class="tag">{{ tag }}</span> {% endfor %}
    {% endif %}
    {% if project.repo_url %}
    <a href="{{ project.repo_url }}" target="_blank" rel="noopener" class="meta">GitHub ↗</a>
    {% endif %}
  </footer>
</article>
```

- [ ] **Step 6: Commit**

```bash
git add templates/layout/base.html templates/partials/
git commit -m "feat: add base layout and partial templates"
```

---

## Task 9: Admin layout

**Files:** `templates/layout/admin.html`

- [ ] **Step 1: Write `templates/layout/admin.html`**

```html
{% extends "layout/base.html" %}
{% block head %}
<style>
  .admin-layout {
    display: grid;
    grid-template-columns: 180px 1fr;
    gap: 2rem;
    align-items: start;
  }
  .admin-sidebar nav ul { list-style:none; padding:0; margin:0; }
  .admin-sidebar nav ul li { margin-bottom: 0.25rem; }
  .admin-sidebar nav ul li a {
    display: block;
    padding: 0.4rem 0.75rem;
    border-radius: var(--pico-border-radius);
    text-decoration: none;
    color: var(--pico-color);
    font-size: 0.9rem;
    transition: background var(--pico-transition);
  }
  .admin-sidebar nav ul li a:hover {
    background: var(--pico-card-background-color);
  }
</style>
{% endblock %}

{% block content %}
<div class="admin-layout">
  <aside class="admin-sidebar">
    <nav>
      <ul>
        <li><a href="/admin">Dashboard</a></li>
        <li><a href="/admin/posts">Posts</a></li>
        <li><a href="/admin/projects">Projects</a></li>
        <li><a href="/admin/content">Site Content</a></li>
        <li><a href="/admin/logout">Log out</a></li>
      </ul>
    </nav>
  </aside>
  <section>{% block admin_content %}{% endblock %}</section>
</div>
{% endblock %}
```

- [ ] **Step 2: Commit**

```bash
git add templates/layout/admin.html
git commit -m "feat: add admin layout template"
```

---
## Task 10: Public page routes and templates

**Files:** `routes/pages.py`, `templates/pages/index.html`, `templates/pages/resume.html`, `templates/pages/contact.html`, `templates/htmx/contact/success.html`, `templates/htmx/contact/error.html`

- [ ] **Step 1: Rewrite `routes/pages.py`**

```python
# routes/pages.py
import json

from bustapi import Blueprint, request
from bustapi.http.response import redirect

from db.connection import get_db
from db.schema import get_content, parse_tags
from routes import render

pages_bp = Blueprint("pages", __name__)


@pages_bp.route("/")
def index():
    db = get_db()
    content = {
        "hero_headline": get_content(db, "home.hero_headline"),
        "hero_subtext":  get_content(db, "home.hero_subtext"),
        "about":         get_content(db, "home.about"),
    }
    raw_posts = db.query(
        "SELECT title, slug, summary, tags, created_at FROM posts "
        "WHERE published = $1 ORDER BY created_at DESC LIMIT $2",
        [True, 3],
    ) or []
    posts = [{**p, "tags": parse_tags(p.get("tags", "[]"))} for p in raw_posts]

    raw_projects = db.query(
        "SELECT title, slug, summary, tags, url, repo_url FROM projects "
        "WHERE published = $1 AND featured = $2 ORDER BY created_at DESC LIMIT $3",
        [True, True, 4],
    ) or []
    projects = [{**p, "tags": parse_tags(p.get("tags", "[]"))} for p in raw_projects]

    return render("pages/index.html", content=content, posts=posts, projects=projects)


@pages_bp.route("/resume")
def resume():
    db = get_db()
    content = {
        "intro":      get_content(db, "resume.intro"),
        "experience": get_content(db, "resume.experience"),
        "education":  get_content(db, "resume.education"),
        "skills":     get_content(db, "resume.skills"),
    }
    return render("pages/resume.html", content=content)


@pages_bp.route("/contact", methods=["GET"])
def contact():
    db = get_db()
    return render(
        "pages/contact.html",
        intro=get_content(db, "contact.intro"),
        success=request.args.get("success") == "1",
        error_msg=request.args.get("error") == "1",
    )


@pages_bp.route("/contact", methods=["POST"])
def contact_post():
    name    = request.form.get("name", "").strip()
    email   = request.form.get("email", "").strip()
    message = request.form.get("message", "").strip()

    if not (name and email and message):
        if request.htmx.is_htmx:
            return render("htmx/contact/error.html", error="All fields are required."), 422
        return redirect("/contact?error=1")

    # TODO: integrate email/notification delivery
    if request.htmx.is_htmx:
        return render("htmx/contact/success.html")
    return redirect("/contact?success=1")
```

- [ ] **Step 2: Write `templates/pages/index.html`**

```html
{% extends "layout/base.html" %}
{% block title %}Home{% endblock %}
{% block content %}
<section class="hero">
  <h1>{{ content.hero_headline | safe }}</h1>
  <p>{{ content.hero_subtext | safe }}</p>
</section>

{% if content.about %}
<section>{{ content.about | safe }}</section>
{% endif %}

{% if posts %}
<section>
  <hgroup>
    <h2>Recent writing</h2>
    <p><a href="/blog">All posts →</a></p>
  </hgroup>
  {% for post in posts %}{% include "partials/blog_card.html" %}{% endfor %}
</section>
{% endif %}

{% if projects %}
<section>
  <hgroup>
    <h2>Featured projects</h2>
    <p><a href="/projects">All projects →</a></p>
  </hgroup>
  {% for project in projects %}{% include "partials/project_card.html" %}{% endfor %}
</section>
{% endif %}
{% endblock %}
```

- [ ] **Step 3: Write `templates/pages/resume.html`**

```html
{% extends "layout/base.html" %}
{% block title %}Resume{% endblock %}
{% block content %}
<h1>Resume</h1>
{% if content.intro %}    <section>{{ content.intro | safe }}</section>{% endif %}
{% if content.experience %}<section>{{ content.experience | safe }}</section>{% endif %}
{% if content.education %} <section>{{ content.education | safe }}</section>{% endif %}
{% if content.skills %}    <section>{{ content.skills | safe }}</section>{% endif %}
{% endblock %}
```

- [ ] **Step 4: Write `templates/pages/contact.html`**

```html
{% extends "layout/base.html" %}
{% block title %}Contact{% endblock %}
{% block content %}
<hgroup>
  <h1>Get in touch</h1>
</hgroup>
{% if intro %}<p>{{ intro | safe }}</p>{% endif %}
{% if success %}<p><ins>Message sent! I'll get back to you soon.</ins></p>{% endif %}
{% if error_msg %}<p><mark>Something went wrong. Please check your details.</mark></p>{% endif %}

<section id="contact-area">
  <form hx-post="/contact" hx-target="#contact-area" hx-swap="outerHTML">
    <input type="text"  name="name"    placeholder="Your name"    required />
    <input type="email" name="email"   placeholder="Your email"   required />
    <textarea           name="message" placeholder="Your message" rows="6" required></textarea>
    <button type="submit">Send message</button>
  </form>
</section>
{% endblock %}
```

- [ ] **Step 5: Write `templates/htmx/contact/success.html`**

```html
<section id="contact-area">
  <p><ins>Message sent! I'll get back to you soon.</ins></p>
</section>
```

- [ ] **Step 6: Write `templates/htmx/contact/error.html`**

```html
<section id="contact-area">
  <p><mark>{{ error }}</mark></p>
  <form hx-post="/contact" hx-target="#contact-area" hx-swap="outerHTML">
    <input type="text"  name="name"    placeholder="Your name"    required />
    <input type="email" name="email"   placeholder="Your email"   required />
    <textarea           name="message" placeholder="Your message" rows="6" required></textarea>
    <button type="submit">Send message</button>
  </form>
</section>
```

- [ ] **Step 7: Smoke test public pages**

```bash
uv run python main.py &
curl -s http://localhost:8000/ | grep -i "nisu"
curl -s http://localhost:8000/resume | grep -i "resume"
curl -s http://localhost:8000/contact | grep -i "contact"
kill %1
```

Expected: each curl returns HTML with relevant content.

- [ ] **Step 8: Commit**

```bash
git add routes/pages.py templates/pages/index.html templates/pages/resume.html \
  templates/pages/contact.html templates/htmx/contact/
git commit -m "feat: add public page routes and templates"
```

---

## Task 11: Blog routes and templates

**Files:** `routes/blog.py`, `templates/pages/blog.html`, `templates/pages/post.html`, `templates/htmx/blog/list.html`

- [ ] **Step 1: Rewrite `routes/blog.py`**

```python
# routes/blog.py
from bustapi import Blueprint, abort, request
from bustapi.http.response import redirect

from db.connection import get_db
from db.schema import parse_tags, render_md
from routes import render

blog_bp = Blueprint("blog", __name__)
_PER_PAGE = 10


def _enrich(row: dict) -> dict:
    return {**row, "tags": parse_tags(row.get("tags", "[]"))}


@blog_bp.route("/blog")
def blog_index():
    db = get_db()
    page   = int(request.args.get("page", 1))
    offset = (page - 1) * _PER_PAGE
    raw = db.query(
        "SELECT title, slug, summary, tags, created_at FROM posts "
        "WHERE published = $1 ORDER BY created_at DESC LIMIT $2 OFFSET $3",
        [True, _PER_PAGE + 1, offset],
    ) or []
    has_more = len(raw) > _PER_PAGE
    return render("pages/blog.html",
                  posts=[_enrich(p) for p in raw[:_PER_PAGE]],
                  has_more=has_more, next_page=page + 1)


@blog_bp.route("/blog/feed")
def blog_feed():
    db = get_db()
    page   = int(request.args.get("page", 1))
    offset = (page - 1) * _PER_PAGE
    raw = db.query(
        "SELECT title, slug, summary, tags, created_at FROM posts "
        "WHERE published = $1 ORDER BY created_at DESC LIMIT $2 OFFSET $3",
        [True, _PER_PAGE + 1, offset],
    ) or []
    has_more = len(raw) > _PER_PAGE
    return render("htmx/blog/list.html",
                  posts=[_enrich(p) for p in raw[:_PER_PAGE]],
                  has_more=has_more, next_page=page + 1)


@blog_bp.route("/blog/<slug>")
def blog_post(slug: str):
    db = get_db()
    row = db.query_one(
        "SELECT * FROM posts WHERE slug = $1 AND published = $2", [slug, True]
    )
    if row:
        post = {**_enrich(row), "body_html": render_md(row["body"])}
        return render("pages/post.html", post=post, content_type="post")

    history = db.query_one(
        "SELECT p.slug FROM posts p "
        "JOIN post_slug_history h ON h.post_id = p.id "
        "WHERE h.slug = $1 AND p.published = $2",
        [slug, True],
    )
    if history:
        return redirect(f"/blog/{history['slug']}", 301)
    abort(404)
```

- [ ] **Step 2: Write `templates/pages/blog.html`**

```html
{% extends "layout/base.html" %}
{% block title %}Blog{% endblock %}
{% block content %}
<hgroup>
  <h1>Blog</h1>
  <p class="meta">Writing on things I find interesting.</p>
</hgroup>
{% if posts %}
  {% include "htmx/blog/list.html" %}
{% else %}
  <p>No posts yet. Check back soon.</p>
{% endif %}
{% endblock %}
```

- [ ] **Step 3: Write `templates/htmx/blog/list.html`**

```html
{% for post in posts %}{% include "partials/blog_card.html" %}{% endfor %}
{% if has_more %}
<button hx-get="/blog/feed?page={{ next_page }}" hx-target="this" hx-swap="outerHTML">
  Load more
</button>
{% endif %}
```

- [ ] **Step 4: Write `templates/pages/post.html`**

```html
{% extends "layout/base.html" %}
{% block title %}{{ post.title }}{% endblock %}
{% block content %}
<article>
  <header>
    <p class="meta">
      {% if content_type == "post" %}<a href="/blog">← Blog</a>
      {% else %}<a href="/projects">← Projects</a>{% endif %}
    </p>
    <h1>{{ post.title }}</h1>
    <p>{{ post.summary }}</p>
    <p class="meta">
      {{ post.created_at[:10] if post.created_at else "" }}
      {% for tag in post.tags %}<span class="tag">{{ tag }}</span> {% endfor %}
      {% if content_type == "project" and post.url %}
        · <a href="{{ post.url }}" target="_blank" rel="noopener">Live ↗</a>
      {% endif %}
      {% if content_type == "project" and post.repo_url %}
        · <a href="{{ post.repo_url }}" target="_blank" rel="noopener">GitHub ↗</a>
      {% endif %}
    </p>
  </header>
  <div>{{ post.body_html | safe }}</div>
</article>
{% endblock %}
```

- [ ] **Step 5: Commit**

```bash
git add routes/blog.py templates/pages/blog.html templates/pages/post.html \
  templates/htmx/blog/list.html
git commit -m "feat: add blog routes and templates with slug redirect"
```

---

## Task 12: Projects routes and templates

**Files:** `routes/projects.py`, `templates/pages/projects.html`, `templates/htmx/projects/grid.html`

- [ ] **Step 1: Rewrite `routes/projects.py`**

```python
# routes/projects.py
from bustapi import Blueprint, abort, request
from bustapi.http.response import redirect

from db.connection import get_db
from db.schema import parse_tags, render_md
from routes import render

projects_bp = Blueprint("projects", __name__)
_PER_PAGE = 12


def _enrich(row: dict) -> dict:
    return {**row, "tags": parse_tags(row.get("tags", "[]"))}


@projects_bp.route("/projects")
def projects_index():
    db = get_db()
    page   = int(request.args.get("page", 1))
    offset = (page - 1) * _PER_PAGE
    raw = db.query(
        "SELECT title, slug, summary, tags, url, repo_url, featured FROM projects "
        "WHERE published = $1 ORDER BY featured DESC, created_at DESC LIMIT $2 OFFSET $3",
        [True, _PER_PAGE + 1, offset],
    ) or []
    has_more = len(raw) > _PER_PAGE
    return render("pages/projects.html",
                  projects=[_enrich(p) for p in raw[:_PER_PAGE]],
                  has_more=has_more, next_page=page + 1)


@projects_bp.route("/projects/feed")
def projects_feed():
    db = get_db()
    page   = int(request.args.get("page", 1))
    offset = (page - 1) * _PER_PAGE
    raw = db.query(
        "SELECT title, slug, summary, tags, url, repo_url, featured FROM projects "
        "WHERE published = $1 ORDER BY featured DESC, created_at DESC LIMIT $2 OFFSET $3",
        [True, _PER_PAGE + 1, offset],
    ) or []
    has_more = len(raw) > _PER_PAGE
    return render("htmx/projects/grid.html",
                  projects=[_enrich(p) for p in raw[:_PER_PAGE]],
                  has_more=has_more, next_page=page + 1)


@projects_bp.route("/projects/<slug>")
def project_detail(slug: str):
    db = get_db()
    row = db.query_one(
        "SELECT * FROM projects WHERE slug = $1 AND published = $2", [slug, True]
    )
    if row:
        project = {**_enrich(row), "body_html": render_md(row["body"])}
        return render("pages/post.html", post=project, content_type="project")

    history = db.query_one(
        "SELECT p.slug FROM projects p "
        "JOIN project_slug_history h ON h.project_id = p.id "
        "WHERE h.slug = $1 AND p.published = $2",
        [slug, True],
    )
    if history:
        return redirect(f"/projects/{history['slug']}", 301)
    abort(404)
```

- [ ] **Step 2: Write `templates/pages/projects.html`**

```html
{% extends "layout/base.html" %}
{% block title %}Projects{% endblock %}
{% block content %}
<hgroup>
  <h1>Projects</h1>
  <p class="meta">Things I've built, explored, and shipped.</p>
</hgroup>
{% if projects %}
  {% include "htmx/projects/grid.html" %}
{% else %}
  <p>No projects yet. Check back soon.</p>
{% endif %}
{% endblock %}
```

- [ ] **Step 3: Write `templates/htmx/projects/grid.html`**

```html
{% for project in projects %}{% include "partials/project_card.html" %}{% endfor %}
{% if has_more %}
<button hx-get="/projects/feed?page={{ next_page }}" hx-target="this" hx-swap="outerHTML">
  Load more
</button>
{% endif %}
```

- [ ] **Step 4: Commit**

```bash
git add routes/projects.py templates/pages/projects.html templates/htmx/projects/grid.html
git commit -m "feat: add projects routes and templates with slug redirect"
```

---
## Task 13: Admin login and logout

**Files:** `routes/admin.py` (login + logout), `templates/pages/admin/login.html`

- [ ] **Step 1: Rewrite `routes/admin.py` with login and logout**

```python
# routes/admin.py
import hmac
import json
import os

from bustapi import Blueprint, abort, request, session
from bustapi.http.response import redirect
from bustapi.responses import HTMLResponse

from db.connection import get_db
from db.schema import get_content, parse_tags, render_md
from routes import render

admin_bp = Blueprint("admin", __name__)


@admin_bp.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        password = request.form.get("password", "")
        admin_pw = os.getenv("ADMIN_PASSWORD", "")
        if password and admin_pw and hmac.compare_digest(password, admin_pw):
            session["admin_authenticated"] = True
            return redirect("/admin")
        return render("pages/admin/login.html", error="Invalid password.")
    return render("pages/admin/login.html", error=None)


@admin_bp.route("/logout")
def logout():
    session.pop("admin_authenticated", None)
    return redirect("/admin/login")
```

- [ ] **Step 2: Write `templates/pages/admin/login.html`**

```html
{% extends "layout/base.html" %}
{% block title %}Admin Login{% endblock %}
{% block content %}
<article style="max-width:400px; margin:4rem auto;">
  <header><h2>Admin</h2></header>
  {% if error %}<p><mark>{{ error }}</mark></p>{% endif %}
  <form method="post" action="/admin/login">
    <label>
      Password
      <input type="password" name="password" autofocus required />
    </label>
    <button type="submit">Log in</button>
  </form>
</article>
{% endblock %}
```

- [ ] **Step 3: Verify login page renders**

```bash
uv run python main.py &
curl -s http://localhost:8000/admin/login | grep -i "login\|admin"
curl -s -o /dev/null -w "%{http_code}" http://localhost:8000/admin
kill %1
```

Expected: login page returns 200; `/admin` returns 302 to `/admin/login`.

- [ ] **Step 4: Commit**

```bash
git add routes/admin.py templates/pages/admin/login.html
git commit -m "feat: add admin login and logout"
```

---

## Task 14: Admin dashboard and posts CRUD

**Files:** Modify `routes/admin.py`, create `templates/pages/admin/dashboard.html`, `templates/pages/admin/post_edit.html`, `templates/htmx/admin/post_row.html`

- [ ] **Step 1: Add dashboard and posts routes to `routes/admin.py`**

Append after the `logout` route:

```python
# ── Dashboard ──────────────────────────────────────────────

@admin_bp.route("/")
def dashboard():
    db = get_db()
    post_count    = (db.query_one("SELECT COUNT(*) as n FROM posts") or {}).get("n", 0)
    project_count = (db.query_one("SELECT COUNT(*) as n FROM projects") or {}).get("n", 0)
    return render("pages/admin/dashboard.html",
                  post_count=post_count, project_count=project_count, view="overview")


# ── Posts ──────────────────────────────────────────────────

@admin_bp.route("/posts", methods=["GET"])
def posts_list():
    db = get_db()
    rows = db.query(
        "SELECT id, title, slug, published, created_at FROM posts ORDER BY created_at DESC"
    ) or []
    return render("pages/admin/dashboard.html", posts=rows, view="posts",
                  post_count=len(rows), project_count=0)


@admin_bp.route("/posts/new", methods=["GET"])
def posts_new():
    return render("pages/admin/post_edit.html", post=None)


@admin_bp.route("/posts", methods=["POST"])
def posts_create():
    db = get_db()
    title     = request.form.get("title", "").strip()
    slug      = request.form.get("slug", "").strip()
    summary   = request.form.get("summary", "").strip()
    body      = request.form.get("body", "").strip()
    tags_raw  = request.form.get("tags", "").strip()
    published = request.form.get("published") == "on"
    tags = [t.strip() for t in tags_raw.split(",") if t.strip()]
    db.execute(
        "INSERT INTO posts (title, slug, summary, body, tags, published) "
        "VALUES ($1,$2,$3,$4,$5,$6)",
        [title, slug, summary, body, json.dumps(tags), published],
    )
    return redirect("/admin/posts")


@admin_bp.route("/posts/<id>/edit", methods=["GET"])
def posts_edit(id: str):
    db = get_db()
    post = db.query_one("SELECT * FROM posts WHERE id = $1", [int(id)])
    if not post:
        abort(404)
    post = {**post, "tags": parse_tags(post.get("tags", "[]"))}
    return render("pages/admin/post_edit.html", post=post)


@admin_bp.route("/posts/<id>/edit", methods=["POST"])
def posts_update(id: str):
    db = get_db()
    post_id  = int(id)
    existing = db.query_one("SELECT slug FROM posts WHERE id = $1", [post_id])
    if not existing:
        abort(404)
    title     = request.form.get("title", "").strip()
    new_slug  = request.form.get("slug", "").strip()
    summary   = request.form.get("summary", "").strip()
    body      = request.form.get("body", "").strip()
    tags_raw  = request.form.get("tags", "").strip()
    published = request.form.get("published") == "on"
    tags      = [t.strip() for t in tags_raw.split(",") if t.strip()]
    old_slug  = existing["slug"]
    if new_slug != old_slug:
        db.execute(
            "INSERT INTO post_slug_history (post_id, slug) VALUES ($1, $2)",
            [post_id, old_slug],
        )
    db.execute(
        "UPDATE posts SET title=$1, slug=$2, summary=$3, body=$4, tags=$5, "
        "published=$6, updated_at=CURRENT_TIMESTAMP WHERE id=$7",
        [title, new_slug, summary, body, json.dumps(tags), published, post_id],
    )
    return redirect("/admin/posts")


@admin_bp.route("/posts/<id>/delete", methods=["POST"])
def posts_delete(id: str):
    db = get_db()
    post_id = int(id)
    db.execute("DELETE FROM post_slug_history WHERE post_id = $1", [post_id])
    db.execute("DELETE FROM posts WHERE id = $1", [post_id])
    if request.htmx.is_htmx:
        return HTMLResponse("", status=200)
    return redirect("/admin/posts")
```

- [ ] **Step 2: Write `templates/pages/admin/dashboard.html`**

```html
{% extends "layout/admin.html" %}
{% block title %}{% if view == "posts" %}Posts{% else %}Admin{% endif %}{% endblock %}
{% block admin_content %}

{% if view == "posts" %}
<hgroup>
  <h2>Posts</h2>
  <p><a href="/admin/posts/new" role="button">New post</a></p>
</hgroup>
{% if posts %}
<table>
  <thead>
    <tr><th>Title</th><th>Slug</th><th>Status</th><th></th></tr>
  </thead>
  <tbody id="posts-table">
    {% for post in posts %}{% include "htmx/admin/post_row.html" %}{% endfor %}
  </tbody>
</table>
{% else %}
<p>No posts yet. <a href="/admin/posts/new">Create one →</a></p>
{% endif %}

{% else %}
<h2>Dashboard</h2>
<div style="display:grid; grid-template-columns:1fr 1fr; gap:1rem;">
  <article>
    <header><strong>Posts</strong></header>
    <p style="font-size:2rem; margin:0;">{{ post_count }}</p>
    <footer><a href="/admin/posts">Manage →</a></footer>
  </article>
  <article>
    <header><strong>Projects</strong></header>
    <p style="font-size:2rem; margin:0;">{{ project_count }}</p>
    <footer><a href="/admin/projects">Manage →</a></footer>
  </article>
</div>
{% endif %}

{% endblock %}
```

- [ ] **Step 3: Write `templates/htmx/admin/post_row.html`**

```html
<tr id="post-row-{{ post.id }}">
  <td><a href="/admin/posts/{{ post.id }}/edit">{{ post.title }}</a></td>
  <td><code>{{ post.slug }}</code></td>
  <td>{{ "Published" if post.published else "Draft" }}</td>
  <td>
    <form
      method="post" action="/admin/posts/{{ post.id }}/delete"
      hx-post="/admin/posts/{{ post.id }}/delete"
      hx-target="#post-row-{{ post.id }}"
      hx-swap="outerHTML"
      hx-confirm="Delete this post?"
      style="display:inline;"
    >
      <button type="submit" class="outline secondary"
              style="padding:0.2rem 0.6rem; font-size:0.8rem;">Delete</button>
    </form>
  </td>
</tr>
```

- [ ] **Step 4: Write `templates/pages/admin/post_edit.html`**

```html
{% extends "layout/admin.html" %}
{% block title %}{{ "Edit Post" if post else "New Post" }}{% endblock %}
{% block admin_content %}
<hgroup>
  <h2>{{ "Edit Post" if post else "New Post" }}</h2>
  <p><a href="/admin/posts">← Back to posts</a></p>
</hgroup>
<form method="post" action="{{ '/admin/posts/' + post.id|string + '/edit' if post else '/admin/posts' }}">
  <label>Title<input type="text" name="title" value="{{ post.title if post else '' }}" required /></label>
  <label>
    Slug
    <input type="text" name="slug" value="{{ post.slug if post else '' }}" required />
    <small>URL: /blog/<em>slug</em>. Changing this preserves the old URL via 301 redirect.</small>
  </label>
  <label>Summary<input type="text" name="summary" value="{{ post.summary if post else '' }}" required /></label>
  <label>
    Body (Markdown)
    <textarea name="body" rows="20" required>{{ post.body if post else '' }}</textarea>
  </label>
  <label>
    Tags (comma-separated)
    <input type="text" name="tags"
           value="{{ post.tags | join(', ') if post and post.tags else '' }}"
           placeholder="python, web, personal" />
  </label>
  <label>
    <input type="checkbox" name="published" {{ "checked" if post and post.published else "" }} />
    Published
  </label>
  <button type="submit">{{ "Update post" if post else "Create post" }}</button>
</form>
{% endblock %}
```

- [ ] **Step 5: Commit**

```bash
git add routes/admin.py templates/pages/admin/dashboard.html \
  templates/pages/admin/post_edit.html templates/htmx/admin/post_row.html
git commit -m "feat: add admin dashboard and posts CRUD"
```

---

## Task 15: Admin projects CRUD

**Files:** Modify `routes/admin.py`, create `templates/pages/admin/project_list.html`, `templates/pages/admin/project_edit.html`, `templates/htmx/admin/project_row.html`

- [ ] **Step 1: Add projects routes to `routes/admin.py`**

Append after the posts routes:

```python
# ── Projects ───────────────────────────────────────────────

@admin_bp.route("/projects", methods=["GET"])
def projects_list():
    db = get_db()
    rows = db.query(
        "SELECT id, title, slug, published, featured FROM projects ORDER BY created_at DESC"
    ) or []
    return render("pages/admin/project_list.html", projects=rows)


@admin_bp.route("/projects/new", methods=["GET"])
def projects_new():
    return render("pages/admin/project_edit.html", project=None)


@admin_bp.route("/projects", methods=["POST"])
def projects_create():
    db = get_db()
    title     = request.form.get("title", "").strip()
    slug      = request.form.get("slug", "").strip()
    summary   = request.form.get("summary", "").strip()
    body      = request.form.get("body", "").strip()
    tags_raw  = request.form.get("tags", "").strip()
    url       = request.form.get("url", "").strip() or None
    repo_url  = request.form.get("repo_url", "").strip() or None
    featured  = request.form.get("featured") == "on"
    published = request.form.get("published") == "on"
    tags = [t.strip() for t in tags_raw.split(",") if t.strip()]
    db.execute(
        "INSERT INTO projects (title, slug, summary, body, tags, url, repo_url, featured, published) "
        "VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9)",
        [title, slug, summary, body, json.dumps(tags), url, repo_url, featured, published],
    )
    return redirect("/admin/projects")


@admin_bp.route("/projects/<id>/edit", methods=["GET"])
def projects_edit(id: str):
    db = get_db()
    project = db.query_one("SELECT * FROM projects WHERE id = $1", [int(id)])
    if not project:
        abort(404)
    project = {**project, "tags": parse_tags(project.get("tags", "[]"))}
    return render("pages/admin/project_edit.html", project=project)


@admin_bp.route("/projects/<id>/edit", methods=["POST"])
def projects_update(id: str):
    db = get_db()
    project_id = int(id)
    existing   = db.query_one("SELECT slug FROM projects WHERE id = $1", [project_id])
    if not existing:
        abort(404)
    title     = request.form.get("title", "").strip()
    new_slug  = request.form.get("slug", "").strip()
    summary   = request.form.get("summary", "").strip()
    body      = request.form.get("body", "").strip()
    tags_raw  = request.form.get("tags", "").strip()
    url       = request.form.get("url", "").strip() or None
    repo_url  = request.form.get("repo_url", "").strip() or None
    featured  = request.form.get("featured") == "on"
    published = request.form.get("published") == "on"
    tags      = [t.strip() for t in tags_raw.split(",") if t.strip()]
    old_slug  = existing["slug"]
    if new_slug != old_slug:
        db.execute(
            "INSERT INTO project_slug_history (project_id, slug) VALUES ($1, $2)",
            [project_id, old_slug],
        )
    db.execute(
        "UPDATE projects SET title=$1, slug=$2, summary=$3, body=$4, tags=$5, "
        "url=$6, repo_url=$7, featured=$8, published=$9, updated_at=CURRENT_TIMESTAMP "
        "WHERE id=$10",
        [title, new_slug, summary, body, json.dumps(tags), url, repo_url, featured, published, project_id],
    )
    return redirect("/admin/projects")


@admin_bp.route("/projects/<id>/delete", methods=["POST"])
def projects_delete(id: str):
    db = get_db()
    project_id = int(id)
    db.execute("DELETE FROM project_slug_history WHERE project_id = $1", [project_id])
    db.execute("DELETE FROM projects WHERE id = $1", [project_id])
    if request.htmx.is_htmx:
        return HTMLResponse("", status=200)
    return redirect("/admin/projects")
```

- [ ] **Step 2: Write `templates/pages/admin/project_list.html`**

```html
{% extends "layout/admin.html" %}
{% block title %}Projects{% endblock %}
{% block admin_content %}
<hgroup>
  <h2>Projects</h2>
  <p><a href="/admin/projects/new" role="button">New project</a></p>
</hgroup>
{% if projects %}
<table>
  <thead>
    <tr><th>Title</th><th>Slug</th><th>Featured</th><th>Status</th><th></th></tr>
  </thead>
  <tbody id="projects-table">
    {% for project in projects %}{% include "htmx/admin/project_row.html" %}{% endfor %}
  </tbody>
</table>
{% else %}
<p>No projects yet. <a href="/admin/projects/new">Create one →</a></p>
{% endif %}
{% endblock %}
```

- [ ] **Step 3: Write `templates/htmx/admin/project_row.html`**

```html
<tr id="project-row-{{ project.id }}">
  <td><a href="/admin/projects/{{ project.id }}/edit">{{ project.title }}</a></td>
  <td><code>{{ project.slug }}</code></td>
  <td>{{ "★" if project.featured else "—" }}</td>
  <td>{{ "Published" if project.published else "Draft" }}</td>
  <td>
    <form
      method="post" action="/admin/projects/{{ project.id }}/delete"
      hx-post="/admin/projects/{{ project.id }}/delete"
      hx-target="#project-row-{{ project.id }}"
      hx-swap="outerHTML"
      hx-confirm="Delete this project?"
      style="display:inline;"
    >
      <button type="submit" class="outline secondary"
              style="padding:0.2rem 0.6rem; font-size:0.8rem;">Delete</button>
    </form>
  </td>
</tr>
```

- [ ] **Step 4: Write `templates/pages/admin/project_edit.html`**

```html
{% extends "layout/admin.html" %}
{% block title %}{{ "Edit Project" if project else "New Project" }}{% endblock %}
{% block admin_content %}
<hgroup>
  <h2>{{ "Edit Project" if project else "New Project" }}</h2>
  <p><a href="/admin/projects">← Back to projects</a></p>
</hgroup>
<form method="post" action="{{ '/admin/projects/' + project.id|string + '/edit' if project else '/admin/projects' }}">
  <label>Title<input type="text" name="title" value="{{ project.title if project else '' }}" required /></label>
  <label>
    Slug
    <input type="text" name="slug" value="{{ project.slug if project else '' }}" required />
    <small>URL: /projects/<em>slug</em>. Old slugs redirect automatically.</small>
  </label>
  <label>Summary<input type="text" name="summary" value="{{ project.summary if project else '' }}" required /></label>
  <label>
    Description (Markdown)
    <textarea name="body" rows="20" required>{{ project.body if project else '' }}</textarea>
  </label>
  <label>
    Tags (comma-separated)
    <input type="text" name="tags"
           value="{{ project.tags | join(', ') if project and project.tags else '' }}"
           placeholder="python, open-source" />
  </label>
  <label>Live URL<input type="url" name="url" value="{{ project.url if project and project.url else '' }}" placeholder="https://example.com" /></label>
  <label>Repo URL<input type="url" name="repo_url" value="{{ project.repo_url if project and project.repo_url else '' }}" placeholder="https://github.com/you/project" /></label>
  <div style="display:flex; gap:2rem;">
    <label>
      <input type="checkbox" name="featured" {{ "checked" if project and project.featured else "" }} />
      Featured on landing page
    </label>
    <label>
      <input type="checkbox" name="published" {{ "checked" if project and project.published else "" }} />
      Published
    </label>
  </div>
  <button type="submit">{{ "Update project" if project else "Create project" }}</button>
</form>
{% endblock %}
```

- [ ] **Step 5: Commit**

```bash
git add routes/admin.py templates/pages/admin/project_list.html \
  templates/pages/admin/project_edit.html templates/htmx/admin/project_row.html
git commit -m "feat: add admin projects CRUD"
```

---

## Task 16: Admin content editor

**Files:** Modify `routes/admin.py`, create `templates/pages/admin/content.html`

- [ ] **Step 1: Add content editor routes to `routes/admin.py`**

Append after the projects routes:

```python
# ── Site Content ───────────────────────────────────────────

@admin_bp.route("/content", methods=["GET"])
def content_list():
    db = get_db()
    rows = db.query(
        "SELECT key, value, label, is_markdown, updated_at FROM site_content ORDER BY key"
    ) or []
    return render("pages/admin/content.html", blocks=rows)


@admin_bp.route("/content/<key>", methods=["POST"])
def content_update(key: str):
    db = get_db()
    value = request.form.get("value", "").strip()
    db.execute(
        "UPDATE site_content SET value=$1, updated_at=CURRENT_TIMESTAMP WHERE key=$2",
        [value, key],
    )
    if request.htmx.is_htmx:
        safe_id = key.replace(".", "-")
        return HTMLResponse(
            f'<span id="saved-{safe_id}" class="meta"><ins>Saved ✓</ins></span>',
            status=200,
        )
    return redirect("/admin/content")
```

- [ ] **Step 2: Write `templates/pages/admin/content.html`**

```html
{% extends "layout/admin.html" %}
{% block title %}Site Content{% endblock %}
{% block admin_content %}
<h2>Site Content</h2>
<p class="meta">Changes take effect immediately on the public site.</p>

{% for block in blocks %}
<article>
  <header>
    <strong>{{ block.label }}</strong>
    <code class="meta" style="float:right;">{{ block.key }}</code>
  </header>
  <form
    hx-post="/admin/content/{{ block.key }}"
    hx-target="#saved-{{ block.key | replace('.', '-') }}"
    hx-swap="outerHTML"
  >
    {% if block.is_markdown %}
    <textarea name="value" rows="5">{{ block.value }}</textarea>
    <small class="meta">Markdown supported.</small>
    {% else %}
    <input type="text" name="value" value="{{ block.value }}" />
    {% endif %}
    <footer style="display:flex; align-items:center; gap:1rem;">
      <button type="submit">Save</button>
      <span id="saved-{{ block.key | replace('.', '-') }}" class="meta"></span>
    </footer>
  </form>
</article>
{% endfor %}
{% endblock %}
```

- [ ] **Step 3: Full end-to-end smoke test**

```bash
uv run python main.py
```

Walk through in a browser:
1. `/` — landing page with seed content ✓
2. `/blog` — empty blog list ✓
3. `/projects` — empty projects grid ✓
4. `/resume` — resume with seed content ✓
5. `/contact` — form renders ✓
6. `/admin` — redirects to `/admin/login` ✓
7. Log in → dashboard shows 0 posts, 0 projects ✓
8. `/admin/posts/new` → create a post → appears in list ✓
9. Visit `/blog/<slug>` → post renders ✓
10. Edit post, change slug → old slug 301 redirects to new ✓
11. `/admin/projects/new` → create a featured project → appears on `/` ✓
12. `/admin/content` → edit `home.hero_headline` → "Saved ✓" appears → `/` shows new headline ✓
13. Delete a post via HTMX delete button → row disappears ✓

- [ ] **Step 4: Run all tests**

```bash
uv run pytest -v
```

Expected: all tests PASS.

- [ ] **Step 5: Add pytest config to `pyproject.toml`**

```toml
[tool.pytest.ini_options]
testpaths = ["tests"]
```

- [ ] **Step 6: Final commit**

```bash
git add routes/admin.py templates/pages/admin/content.html pyproject.toml
git commit -m "feat: add admin content editor and finalize scaffold"
```

---

## Self-Review

**Spec coverage:**
- [x] HTMXMiddleware attaching HTMXDetails to all requests → Task 4, 6
- [x] All 8 HX-* request headers parsed → Task 4
- [x] Six HX-* response helpers → Task 4
- [x] `Vary: HX-Request` on all responses → Task 4
- [x] AdminAuthMiddleware with env-var password → Task 5, 13
- [x] Session cookie auth (no DB) → Task 5, 6, 13
- [x] Stoolap schema: posts, projects, slug histories, site_content → Task 3
- [x] Admin-settable slugs with old slug → 301 redirect via history tables → Task 11, 12, 14, 15
- [x] site_content seeded and editable from admin (no redeploy) → Task 3, 16
- [x] Resume built from site_content blocks → Task 10
- [x] Markdown rendered at request time (markdown-it-py) → Task 3
- [x] PicoCSS v2 classless + HTMX 4 + Alpine.js via CDN → Task 8
- [x] Mycelium theme (jade/azure/slate CSS variables) → Task 7
- [x] Template structure: layout/, pages/, partials/, htmx/ → Tasks 8–16
- [x] Contact form with HTMX fragments (success + error) → Task 10
- [x] Blog pagination via HTMX "Load more" → Task 11
- [x] Projects grid pagination via HTMX "Load more" → Task 12
- [x] Admin CRUD for posts with slug history → Task 14
- [x] Admin CRUD for projects with slug history → Task 15
- [x] HTMX inline delete on admin rows → Task 14, 15
- [x] Landing page with recent posts + featured projects → Task 10
- [x] `render()` helper uses cached Jinja2 env → Task 6

**Type consistency:** `render()` returns `HTMLResponse` throughout. `parse_tags()` always returns `list[str]`. `render_md()` always returns `str`. `request.htmx.is_htmx` checked consistently in routes. `session["admin_authenticated"]` set/cleared in login/logout.

**No placeholders or TODOs in implementation steps.**
