# syntax=docker/dockerfile:1
FROM python:3.13-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

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

EXPOSE 8000

CMD ["uv", "run", "litestar", "run", "--host", "0.0.0.0", "--port", "8000"]
