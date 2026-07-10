# syntax=docker/dockerfile:1
FROM python:3.13-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# Install uv for fast dependency resolution.
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# Install dependencies first (cached layer).
COPY pyproject.toml uv.lock .python-version ./
RUN uv sync --frozen --no-dev --no-install-project

# Copy application code.
COPY . .

# Install the project itself.
RUN uv sync --frozen --no-dev

# Create data directories.
RUN mkdir -p data/media data/md

# Create a non-root user and give it ownership of the app + data dirs.
RUN groupadd --system garden && useradd --system --gid garden --home-dir /app garden \
    && chown -R garden:garden /app

USER garden

EXPOSE 8000

# The entrypoint runs Piccolo migrations before exec'ing the server CMD,
# so a fresh Postgres bootstraps the schema automatically.
COPY --chown=garden:garden scripts/entrypoint.sh /app/entrypoint.sh
ENTRYPOINT ["/app/entrypoint.sh"]
CMD ["uv", "run", "litestar", "run", "--host", "0.0.0.0", "--port", "8000"]