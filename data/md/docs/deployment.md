# Deployment

## Docker

Garden CMS ships with a `Containerfile` and `compose.yaml` for container-based deployment.

### Quick start with Docker Compose

```bash
docker compose up -d
```

This starts the application and a PostgreSQL database. The app is available at `http://localhost:8000`.

### Production Compose

Create a `.env` file with your production settings:

```bash
DATABASE_URL=postgres://garden:secure-password@db:5432/garden
SECRET_KEY=your-random-secret-key
ADMIN_PASSWORD=your-admin-password
```

Then run:

```bash
docker compose --profile production up -d
```

### Building the image

```bash
docker build -f Containerfile -t garden-cms .
```

## Environment variables

See [Configuration](configuration) for the complete list.

## Stateless mode

Set `STATELESS=true` for serverless or multi-instance deployments:

```bash
STATELESS=true
```

In stateless mode, content blocks and storage settings are reloaded from the database on every request instead of being cached in memory. This ensures consistency when multiple instances share a database or when instances are ephemeral (e.g. AWS Lambda, Cloud Run, Fly Machines).

When stateless mode is inactive (default), content is cached in memory at startup and refreshed only when saved through the admin. This is more performant for single-instance deployments.

## Reverse proxy

Garden CMS runs as a standard ASGI application on port 8000. Place it behind a reverse proxy (Caddy, nginx, Traefik) for TLS termination:

```
# Caddyfile example
yoursite.com {
    reverse_proxy garden-cms:8000
}
```

## Security headers

The application sets these headers on all responses:

- `X-Frame-Options: DENY`
- `X-Content-Type-Options: nosniff`
- `X-XSS-Protection: 1; mode=block`
- `Referrer-Policy: strict-origin-when-cross-origin`
- `Vary: HX-Request`

## Database migrations

After upgrading, run Piccolo migrations:

```bash
uv run piccolo migrations forwards db
```

Or in Docker:

```bash
docker compose exec app uv run piccolo migrations forwards db
```

## Hosting

Garden CMS runs as a standard Python ASGI application. It can be deployed to traditional servers, container platforms, or serverless environments. Your choice depends on traffic patterns, budget, and operational preferences.

### Stateful hosting

In stateful mode (the default), Garden CMS caches content blocks and storage settings in memory at startup. This is the most performant option for single-instance deployments where the process stays running.

#### Requirements

- A long-running Python process (not ephemeral)
- PostgreSQL database
- Persistent disk for local media storage, or an S3-compatible bucket

#### Providers

| Provider                      | Notes                                                                                                                                   |
| ----------------------------- | --------------------------------------------------------------------------------------------------------------------------------------- |
| **Fly.io**                    | Deploy the Containerfile directly with `fly launch`. Attach a Fly Postgres cluster. Persistent volumes available for local media.       |
| **Railway**                   | Connect a GitHub repo or push the container image. Managed PostgreSQL add-on. Works out of the box with the included `compose.yaml`.    |
| **Render**                    | Web service from Dockerfile with managed PostgreSQL. Free tier available. Set environment variables in the dashboard.                   |
| **DigitalOcean App Platform** | Container-based deployment with managed Postgres. Supports persistent volumes for media.                                                |
| **Hetzner Cloud + Coolify**   | Low-cost VPS with Coolify for self-hosted PaaS. Run `docker compose up -d` or deploy via Git.                                           |
| **Self-hosted VPS**           | Any Linux server with Docker or a Python runtime. Use the provided `compose.yaml` with a reverse proxy (Caddy, nginx, Traefik) for TLS. |

#### Example: Fly.io

```bash
fly launch --dockerfile Containerfile
fly postgres create
fly postgres attach
fly secrets set SECRET_KEY=your-random-key ADMIN_PASSWORD=your-password
fly deploy
```

#### Example: Docker on a VPS

```bash
git clone https://github.com/itsnisuxyz/garden-cms.git
cd garden-cms
cp .env.example .env  # edit with your settings
docker compose up -d
```

Place behind a reverse proxy for TLS:

```
# Caddyfile
yoursite.com {
    reverse_proxy localhost:8000
}
```

### Serverless hosting

Set `STATELESS=true` for serverless environments. In this mode, content blocks and storage settings are reloaded from the database on every request instead of being cached in memory. This ensures consistency when instances are ephemeral or when multiple instances run concurrently.

#### Requirements

- A serverless platform that supports ASGI or container-based functions
- An externally hosted PostgreSQL database (not co-located with the function)
- S3-compatible storage for media (local disk is not available in ephemeral environments)

#### Providers

| Provider                             | Notes                                                                                                                                                        |
| ------------------------------------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| **[Phemeral](https://phemeral.dev)** | Zero-config ASGI deployment. Create a project in the dashboard, link your repo, and push. Auto-detects any ASGI-compatible app.                              |
| **Fly.io**                           | Deploy the Containerfile with `fly launch`. Use Fly Machines for scale-to-zero. Attach Fly Postgres or an external database.                                 |
| **Railway**                          | Connect a GitHub repo or push the container image. Managed PostgreSQL add-on. Set `STATELESS=true` in the dashboard.                                         |
| **Render**                           | Web service from Dockerfile with managed PostgreSQL. Supports auto-scaling and zero-instance scale-down on paid plans.                                       |
| **Google Cloud Run**                 | Deploy the container image directly. Cloud Run scales to zero and supports concurrency. Use Cloud SQL for PostgreSQL, GCS (via S3-compatible API) for media. |
| **AWS Lambda + Mangum**              | Wrap the Litestar app with [Mangum](https://mangum.fastapiexpert.com/) for Lambda compatibility. Use RDS or Aurora for PostgreSQL, S3 for media.             |
| **Azure Container Apps**             | Serverless containers with scale-to-zero. Use Azure Database for PostgreSQL and Azure Blob Storage.                                                          |
| **Vercel (via container)**           | Experimental container runtime support. Pair with Neon or Supabase for PostgreSQL.                                                                           |
| **Neon + Cloudflare R2**             | Serverless PostgreSQL (Neon) with S3-compatible object storage (R2). Works with any compute platform.                                                        |

#### Environment variables for serverless

```bash
STATELESS=true
DATABASE_URL=postgres://user:pass@your-managed-db:5432/garden
SECRET_KEY=your-random-key
ADMIN_PASSWORD=your-password
S3_BUCKET=your-bucket
S3_REGION=us-east-1
S3_ACCESS_KEY_ID=your-key
S3_SECRET_ACCESS_KEY=your-secret
S3_PUBLIC_URL=https://cdn.yoursite.com
```

#### Example: Phemeral

1. Create a project in the [Phemeral dashboard](https://phemeral.dev)
2. Link your repository
3. Push a commit

Phemeral auto-detects the ASGI application and deploys it. Set your environment variables (`STATELESS=true`, `DATABASE_URL`, `SECRET_KEY`, etc.) in the project settings.

#### Example: Google Cloud Run

```bash
# Build and push
gcloud builds submit --tag gcr.io/PROJECT/garden-cms

# Deploy
gcloud run deploy garden-cms \
  --image gcr.io/PROJECT/garden-cms \
  --set-env-vars STATELESS=true,DATABASE_URL=postgres://... \
  --allow-unauthenticated
```

### Database hosting

Garden CMS requires PostgreSQL 14+. For managed options:

| Provider                    | Free tier             | Notes                                         |
| --------------------------- | --------------------- | --------------------------------------------- |
| **Neon**                    | Yes (0.5 GB)          | Serverless Postgres, branching, scale-to-zero |
| **Supabase**                | Yes (500 MB)          | Managed Postgres with extras                  |
| **Railway**                 | Trial credits         | Managed Postgres add-on                       |
| **Fly Postgres**            | Included in compute   | Runs alongside your app                       |
| **AWS RDS / Aurora**        | Free tier (12 months) | Production-grade managed Postgres             |
| **DigitalOcean Managed DB** | No                    | Starts at $15/month                           |

### Choosing between stateful and serverless

| Consideration        | Stateful                   | Serverless                             |
| -------------------- | -------------------------- | -------------------------------------- |
| Latency              | Lower (cached content)     | Slightly higher (DB reads per request) |
| Scaling              | Vertical (single instance) | Horizontal (auto-scaling)              |
| Cold starts          | None                       | Platform-dependent                     |
| Media storage        | Local disk or S3           | S3 required                            |
| Cost at low traffic  | Fixed server cost          | Near-zero (scale to zero)              |
| Cost at high traffic | Predictable                | Variable                               |
| Complexity           | Lower                      | Higher (managed DB + S3 required)      |
