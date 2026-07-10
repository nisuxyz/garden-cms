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
- **45 classless CSS framework presets** built in
- **Stateless mode** for serverless and multi-instance deployments
- **JinjaX components** — `<CollectionFeed>`, `<MediaImage>`, and custom components
- **Admin interface** — HTMX-powered with live preview, syntax-highlighted editors, and drag reordering
- **CSRF protection** on all mutating endpoints

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
cp .env.example .env   # then edit .env and set SECRET_KEY + ADMIN_PASSWORD
docker compose up -d
```

The app runs migrations automatically on boot. It is available at [http://localhost:8000](http://localhost:8000) and the admin at [http://localhost:8000/admin](http://localhost:8000/admin).

### From source

Requires Python 3.13+, PostgreSQL, and [uv](https://docs.astral.sh/uv/).

```bash
git clone https://github.com/itsnisuxyz/garden-cms.git
cd garden-cms
uv sync
```

Create a database and run migrations:

```bash
createdb garden
uv run piccolo migrations forwards db
```

Set an admin password and start the server:

```bash
export ADMIN_PASSWORD=your-password
uv run litestar run --reload
```

## Configuration

Configuration is via environment variables. Copy `.env.example` to `.env` and edit it.

### Env var management with dotenvx

For production, [dotenvx](https://dotenvx.com) is recommended for managing secrets. It encrypts `.env` files at rest and injects values at process start:

```bash
npm install -g dotenvx
cp .env.example .env
dotenvx set SECRET_KEY "$(openssl rand -hex 32)"
dotenvx set ADMIN_PASSWORD "your-password"
dotenvx run -- uv run litestar run --host 0.0.0.0
```

### Core variables

| Variable         | Description                              | Default                                              |
| ---------------- | ---------------------------------------- | ---------------------------------------------------- |
| `DATABASE_URL`   | PostgreSQL connection string             | `postgresql://postgres:postgres@localhost:5432/garden` |
| `SECRET_KEY`     | Session/CSRF signing key (use ≥32 bytes) | `dev-secret-change-me` (dev only; **fails fast in prod**) |
| `ADMIN_PASSWORD` | Admin login password                     | _(unset)_                                            |
| `STATELESS`      | Reload from DB every request             | `false`                                              |
| `DEBUG`          | Enable debug mode                        | `false`                                              |

> **Warning:** If `SECRET_KEY` is unset or the dev default in a non-dev deployment (no `localhost` in `DATABASE_URL` and `DEBUG=false`), the app refuses to start. Generate a strong key with `openssl rand -hex 32`.

### OAuth2 / OIDC

| Variable              | Description                                  | Default     |
| --------------------- | -------------------------------------------- | ----------- |
| `OAUTH_CLIENT_ID`     | OAuth2/OIDC client ID                        | _(unset)_   |
| `OAUTH_CLIENT_SECRET` | OAuth2/OIDC client secret                    | _(unset)_   |
| `OAUTH_ISSUER_URL`    | OAuth provider issuer URL                    | _(unset)_   |
| `OAUTH_REDIRECT_URI`  | OAuth callback URL                           | _(unset)_   |
| `OAUTH_ALLOWED_GROUP` | Restrict admin access to this group          | _(unset)_   |
| `OAUTH_PROVIDER_NAME` | Display name for the OAuth provider          | `oauth`     |

> **Warning:** If `OAUTH_ALLOWED_GROUP` is empty, **any authenticated user** is granted admin access. Always set it in production.

### Storage

Configurable in the admin Settings page or via env vars (env vars are the fallback when no DB setting exists).

| Variable               | Description                             | Default     |
| ---------------------- | --------------------------------------- | ----------- |
| `STORAGE_BACKEND`      | `local` or `s3`                         | `local`     |
| `S3_BUCKET`            | S3-compatible bucket name               | _(unset)_   |
| `S3_REGION`            | S3 region                               | `us-east-1` |
| `S3_ENDPOINT_URL`      | Custom S3 endpoint (R2, MinIO)          | _(unset)_   |
| `S3_ACCESS_KEY_ID`     | S3 access key                           | _(unset)_   |
| `S3_SECRET_ACCESS_KEY` | S3 secret key (write-only in the admin) | _(unset)_   |
| `S3_PREFIX`            | Object key prefix                       | _(unset)_   |
| `S3_PUBLIC_URL`        | Public CDN URL for direct media serving | _(unset)_   |

See the [full configuration reference](data/md/docs/configuration.md) for all settings.

## Documentation

Documentation is included in `data/md/docs/` and served by the application itself when the `docs` markdown mount is configured in the admin.

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