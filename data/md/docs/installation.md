# Installation

## Requirements

- Python 3.13 or later
- PostgreSQL 14 or later
- [uv](https://docs.astral.sh/uv/) package manager (recommended) or pip

## Setup

Clone the repository and install dependencies:

```bash
git clone https://github.com/itsnisuxyz/garden-cms.git
cd garden-cms
uv sync
```

## Database

Create a PostgreSQL database:

```bash
createdb bussin
```

Run migrations:

```bash
uv run piccolo migrations forwards db
uv run piccolo migrations forwards user
uv run piccolo migrations forwards session_auth
```

## Environment variables

Create a `.env` file in the project root:

```bash
DATABASE_URL=postgres://postgres:postgres@localhost:5432/bussin
SECRET_KEY=change-me-to-a-random-string
```

See [Configuration](/docs/configuration) for the full list of environment variables.

## Start the server

```bash
uv run litestar run --reload
```

The admin interface is available at `http://localhost:8000/admin`. On first run, Garden CMS seeds the database with a default theme, sample pages, and two collections (Blog and Projects).

## Admin password

Set the `ADMIN_PASSWORD` environment variable to enable password login:

```bash
ADMIN_PASSWORD=your-password
```

Alternatively, configure [OAuth authentication](/docs/authentication) for SSO.
