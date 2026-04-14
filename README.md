# Garden CMS

A lightweight, database-driven content management system built with Python. Full control over markup, theming, and deployment.

## Features

- **Pages** with Jinja2 template bodies and configurable navigation
- **Content blocks** — global key/value pairs available in all templates as `{{ site.key }}`
- **Collections** — structured content types with custom fields, card/detail templates, and HTMX-powered paginated feeds
- **Themes** — Jinja2 base templates with CSS and per-page overrides
- **Media uploads** — local disk or S3-compatible storage with CDN support
- **Markdown mounts** — serve directories of `.md` files as themed pages with file-based routing
- **Authentication** — password login or OAuth2/OIDC with PKCE
- **48 classless CSS framework presets** built in
- **Stateless mode** for serverless and multi-instance deployments
- **JinjaX components** — `<CollectionFeed>`, `<MediaImage>`, and custom components
- **Admin interface** — HTMX-powered with live preview, syntax-highlighted editors, and drag reordering

## Stack

| Component | Technology                                     |
| --------- | ---------------------------------------------- |
| Framework | [Litestar](https://litestar.dev) (Python ASGI) |
| ORM       | [Piccolo](https://piccolo-orm.com)             |
| Database  | PostgreSQL                                     |
| Templates | Jinja2 + [JinjaX](https://jinjax.scaletti.dev) |
| Admin UI  | HTMX + [Pico CSS](https://picocss.com)         |

## Quick start

### With Docker Compose

```bash
git clone https://github.com/itsnisuxyz/garden-cms.git
cd garden-cms
docker compose up -d
```

The app is available at [http://localhost:8000](http://localhost:8000) and the admin at [http://localhost:8000/admin](http://localhost:8000/admin).

### From source

Requires Python 3.13+, PostgreSQL, and [uv](https://docs.astral.sh/uv/).

```bash
git clone https://github.com/itsnisuxyz/garden-cms.git
cd garden-cms
uv sync
```

Create a database and run migrations:

```bash
createdb bussin
uv run piccolo migrations forwards db
uv run piccolo migrations forwards user
uv run piccolo migrations forwards session_auth
```

Set an admin password and start the server:

```bash
export ADMIN_PASSWORD=your-password
uv run litestar run --reload
```

## Configuration

Configuration is done via environment variables. Create a `.env` file:

```bash
DATABASE_URL=postgres://postgres:postgres@localhost:5432/bussin
SECRET_KEY=change-me-to-a-random-string
ADMIN_PASSWORD=your-password
```

| Variable         | Description                  | Default                                              |
| ---------------- | ---------------------------- | ---------------------------------------------------- |
| `DATABASE_URL`   | PostgreSQL connection string | `postgres://postgres:postgres@localhost:5432/bussin` |
| `SECRET_KEY`     | Session encryption key       | `dev-secret-change-me`                               |
| `ADMIN_PASSWORD` | Admin login password         | _(unset)_                                            |
| `STATELESS`      | Reload from DB every request | `false`                                              |

See the [full configuration reference](https://yoursite.com/docs/configuration) for storage, OAuth, and all other settings.

## Documentation

Documentation is included in `data/md/docs/` and served by the application itself when mounted at `/docs` in the admin Markdown section.

## Development

```bash
uv sync
uv run litestar run --reload
```

### Tests

```bash
uv run python -m pytest tests/ -x -q
```

## License

MIT
