# Docs

Garden CMS is a lightweight, database-driven content management system built with Python. It gives you full control over markup, theming, and deployment while providing a clean admin interface for content management.

## Overview

- **Pages** — Create and manage pages with Jinja2 template bodies, per-page theme overrides, and configurable navigation order
- **Content Blocks** — Global key/value pairs (text, HTML, or image references) available in all templates as `{{ site.key }}`
- **Collections** — Define structured content types with custom field schemas, card/detail templates, and HTMX-powered paginated feeds
- **Themes** — Jinja2 base templates with CSS, light/dark mode support, and per-page overrides
- **Media** — Upload images with pluggable storage backends (local disk or S3-compatible)
- **Markdown Mounts** — Map directories of `.md` files to URL routes with file-based routing
- **Authentication** — Password login or OAuth2/OIDC with PKCE (e.g. Pocket ID, Authentik, Keycloak)

## Stack

| Component    | Technology                                                |
| ------------ | --------------------------------------------------------- |
| Framework    | [Litestar](https://litestar.dev) (Python ASGI)            |
| ORM          | [Piccolo](https://piccolo-orm.com)                        |
| Database     | PostgreSQL                                                |
| Templates    | Jinja2 + [JinjaX](https://jinjax.scaletti.dev) components |
| Admin UI     | HTMX + Pico CSS                                           |
| Code editors | CodeJar + Prism.js                                        |

## More

- [Installation](/docs/installation) — Requirements, setup, and environment variables
- [Getting Started](/docs//getting-started) — First steps after installation
- [Pages](/docs/pages) — Creating and managing pages
- [Content Blocks](/docs/content-blocks) — Global template variables
- [Collections](/docs/collections) — Structured content types and feeds
- [Themes](/docs/themes) — Theming system and base templates
- [Media](/docs/media) — File uploads and storage backends
- [Markdown Mounts](/docs/markdown-mounts) — File-based markdown routing
- [Templates](/docs/templates) — Jinja2 templating reference
- [Authentication](/docs/authentication) — Password and OAuth login
- [Deployment](/docs/deployment) — Docker, serverless, and production configuration
- [Configuration](/docs/configuration) — All environment variables and settings
