# Personal Site Scaffold — Design Spec

**Date:** 2026-04-03
**Project:** itsnisuxyz-bussin
**Stack:** BustAPI · HTMX 4.x · Alpine.js · PicoCSS (classless) · Stoolap

---

## 1. Purpose

A polished, production-quality personal site. Not strictly career-focused — equally a showcase for hobbies, projects, and life as it is for professional work. Content (blog posts, projects, resume text, site copy) is editable via an admin UI without redeployment. Layout and styling changes require a redeploy.

---

## 2. Project Structure

```
itsnisuxyz-bussin/
├── main.py                        # App init, middleware + blueprint registration, run
├── middleware/
│   ├── __init__.py
│   ├── htmx.py                    # HTMXMiddleware + HTMXDetails + response helpers
│   └── auth.py                    # AdminAuthMiddleware — guards /admin/* routes
├── routes/
│   ├── __init__.py
│   ├── pages.py                   # /, /resume, /contact
│   ├── blog.py                    # /blog, /blog/<slug>, /blog/feed
│   ├── projects.py                # /projects, /projects/<slug>, /projects/feed
│   └── admin.py                   # /admin/*, CRUD for posts, projects, content
├── db/
│   ├── __init__.py
│   ├── connection.py              # Stoolap DB open, get_db() helper
│   └── schema.py                  # CREATE TABLE IF NOT EXISTS, seed site_content
├── templates/
│   ├── layout/
│   │   ├── base.html              # Main layout: PicoCSS, Alpine, HTMX CDN, nav, footer
│   │   └── admin.html             # Admin layout: extends base, sidebar nav
│   ├── pages/
│   │   ├── index.html
│   │   ├── blog.html
│   │   ├── post.html              # Shared for blog posts and project detail
│   │   ├── projects.html
│   │   ├── resume.html
│   │   ├── contact.html
│   │   └── admin/
│   │       ├── login.html
│   │       ├── dashboard.html
│   │       ├── post_edit.html
│   │       ├── project_edit.html
│   │       └── content.html
│   ├── partials/
│   │   ├── nav.html
│   │   ├── footer.html
│   │   ├── blog_card.html
│   │   └── project_card.html
│   └── htmx/
│       ├── blog/
│       │   └── list.html          # Paginated blog card list fragment
│       ├── projects/
│       │   └── grid.html          # Projects grid fragment
│       ├── contact/
│       │   ├── success.html
│       │   └── error.html
│       └── admin/
│           ├── post_row.html
│           └── project_row.html
└── static/
    └── css/
        └── theme.css              # PicoCSS variable overrides only
```

---

## 3. HTMX Middleware

### HTMXDetails

Attached to every request as `request.htmx`. Always present — non-HTMX requests get an instance where `is_htmx` is `False` and all other properties are `None`/`False`.

| Property | Source Header | Type |
|---|---|---|
| `is_htmx` | `HX-Request` | `bool` |
| `request_type` | `HX-Request-Type` | `str \| None` |
| `current_url` | `HX-Current-URL` | `str \| None` |
| `source` | `HX-Source` | `str \| None` |
| `target` | `HX-Target` | `str \| None` |
| `boosted` | `HX-Boosted` | `bool` |
| `history_restore` | `HX-History-Restore-Request` | `bool` |
| `last_event_id` | `Last-Event-ID` | `str \| None` |

### HTMXMiddleware

- `process_request`: instantiates `HTMXDetails` from request headers, attaches as `request.htmx`
- `process_response`: adds `Vary: HX-Request` to every response

### Response helpers (functions in `middleware/htmx.py`)

Each takes a `Response` and returns it with the appropriate header added:

| Helper | Header set | Effect |
|---|---|---|
| `hx_redirect(response, url)` | `HX-Redirect` | Client-side redirect with page reload |
| `hx_location(response, url, **opts)` | `HX-Location` | AJAX navigation, no reload |
| `hx_refresh(response)` | `HX-Refresh: true` | Force full page refresh |
| `hx_push_url(response, url)` | `HX-Push-Url` | Push URL to browser history |
| `hx_replace_url(response, url)` | `HX-Replace-Url` | Replace current history entry |
| `hx_trigger(response, event, **detail)` | `HX-Trigger` | Fire a client-side event |

### AdminAuthMiddleware

- `process_request`: if path starts with `/admin` (excluding `/admin/login`), checks for a valid session cookie. If missing or invalid, short-circuits with a redirect to `/admin/login`.
- Password is matched against the `ADMIN_PASSWORD` environment variable.
- No database involvement — session cookie only.

---

## 4. Database Schema

```sql
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
```

### Slug redirect behavior

Routes for `/blog/<slug>` and `/projects/<slug>` check the live table first. On miss, they check `post_slug_history` / `project_slug_history` and issue a `301` redirect to the current canonical slug. All slug values are unique across their respective history table to prevent collisions.

### site_content seed keys

Seeded on first run (`INSERT OR IGNORE`):

| key | label |
|---|---|
| `home.hero_headline` | Landing page headline |
| `home.hero_subtext` | Landing page subtext |
| `home.about` | About blurb |
| `resume.intro` | Resume intro paragraph |
| `resume.experience` | Experience section |
| `resume.education` | Education section |
| `resume.skills` | Skills section |
| `contact.intro` | Contact page intro text |

`get_content(db, key)` returns the value rendered to HTML (if `is_markdown`) or raw text, with empty string fallback.

### Markdown rendering

`body` and markdown `site_content` values are rendered at request time using `markdown-it-py`.

### Database connection

`DATABASE_URL` env var, defaulting to `./data/site.db`. `db/schema.py` runs on startup before the server accepts requests.

---

## 5. Routes

### Public (`routes/pages.py`)

| Method | Path | Returns | HTMX behavior |
|---|---|---|---|
| GET | `/` | `pages/index.html` | — |
| GET | `/resume` | `pages/resume.html` | — |
| GET | `/contact` | `pages/contact.html` | — |
| POST | `/contact` | redirect or fragment | Full page → redirect; HTMX → `htmx/contact/success.html` or `htmx/contact/error.html` |

### Blog (`routes/blog.py`)

| Method | Path | Returns |
|---|---|---|
| GET | `/blog` | `pages/blog.html` with initial post list |
| GET | `/blog/<slug>` | `pages/post.html` (`content_type="post"` in context), or 301 if old slug |
| GET | `/blog/feed` | `htmx/blog/list.html` fragment (pagination) |

### Projects (`routes/projects.py`)

| Method | Path | Returns |
|---|---|---|
| GET | `/projects` | `pages/projects.html` with initial grid |
| GET | `/projects/<slug>` | `pages/post.html` (shared template, `content_type="project"` in context), or 301 if old slug |
| GET | `/projects/feed` | `htmx/projects/grid.html` fragment |

### Admin (`routes/admin.py`) — all guarded by AdminAuthMiddleware

| Method | Path | Purpose |
|---|---|---|
| GET/POST | `/admin/login` | Login form |
| GET | `/admin/logout` | Clear session, redirect to login |
| GET | `/admin` | Dashboard overview |
| GET/POST | `/admin/posts` | List posts, create new |
| GET/POST | `/admin/posts/<id>/edit` | Edit post |
| POST | `/admin/posts/<id>/delete` | Delete post |
| GET/POST | `/admin/projects` | List projects, create new |
| GET/POST | `/admin/projects/<id>/edit` | Edit project |
| POST | `/admin/projects/<id>/delete` | Delete project |
| GET | `/admin/content` | List all content keys |
| POST | `/admin/content/<key>` | Update a content block |

---

## 6. Theme

**Concept:** *Mycelium* — the quiet, invisible network beneath a forest. Calm organic tones with cool technological accents, as if nature and silicon are growing together.

**Implementation:** PicoCSS CSS variable overrides in `static/css/theme.css` only. No custom utility classes. All markup is semantic HTML5.

### Color palette (PicoCSS color tokens)

| Role | Light mode | Dark mode |
|---|---|---|
| Primary (links, buttons, focus) | `jade-550` | `jade-400` |
| Secondary (accents, tags) | `azure-600` | `azure-400` |
| Background | `slate-50` | `slate-950` |
| Card/surface | `white` | `slate-900` |
| Muted text | `slate-500` | `slate-400` |
| Border | `slate-200` | `slate-800` |

### Typography

System sans-serif stack for body. Monospace stack for code blocks and subtle UI labels (tags, dates).

### Shape & Motion

- `--pico-border-radius: 0.5rem` — organic but not bubbly
- Subtle box shadows on cards only
- Transitions: `150ms ease` — responsive but unhurried

### CDN assets (loaded in `layout/base.html`)

- PicoCSS classless CDN
- HTMX 4.x CDN
- Alpine.js CDN
- `static/css/theme.css` loaded after PicoCSS to override variables

---

## 7. Dependencies to add

Make sure to use uv:

- `markdown-it-py` — markdown rendering
- `python-dotenv` — env var loading
- `stoolap` — embedded database