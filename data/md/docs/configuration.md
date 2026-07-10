# Configuration

All configuration is done via environment variables. Settings with a default value are optional.

## Core

| Variable       | Description                                        | Default                                                |
| -------------- | -------------------------------------------------- | ------------------------------------------------------ |
| `DATABASE_URL` | PostgreSQL connection string                       | `postgresql://postgres:postgres@localhost:5432/garden` |
| `SECRET_KEY`   | Session/CSRF signing key (≥32 bytes recommended)   | `dev-secret-change-me` (dev only; **fails fast in prod**) |
| `ADMIN_PASSWORD` | Password for admin login                         | _(unset, login disabled unless OAuth configured)_     |
| `DEBUG`        | Enable debug mode                                  | `false`                                                |

> **Warning:** `SECRET_KEY` defaults to an insecure dev value. In a non-dev deployment (no `localhost` in `DATABASE_URL` and `DEBUG=false`) the app refuses to start until you set a real key. Generate one with `openssl rand -hex 32`.

## Authentication

| Variable              | Description                              | Default                                           |
| --------------------- | ---------------------------------------- | ------------------------------------------------- |
| `OAUTH_CLIENT_ID`     | OAuth2/OIDC client ID                    | _(unset)_                                         |
| `OAUTH_CLIENT_SECRET` | OAuth2/OIDC client secret                | _(unset)_                                         |
| `OAUTH_ISSUER_URL`    | OAuth provider issuer URL                | _(unset)_                                         |
| `OAUTH_REDIRECT_URI`  | OAuth callback URL                       | _(unset)_                                         |
| `OAUTH_ALLOWED_GROUP` | Restrict admin access to this group      | _(unset, **any authenticated user is admin**)_    |
| `OAUTH_SCOPE`         | OAuth scopes requested                   | `openid profile email groups`                     |
| `OAUTH_PROVIDER_NAME` | Display name for the OAuth provider      | `oauth`                                           |

> **Warning:** If `OAUTH_ALLOWED_GROUP` is empty, **any user who can authenticate against the issuer is granted admin access.** Always set it in production.

## Storage

These can also be configured in **Settings** in the admin. Environment variables take effect as fallbacks when no database setting exists. The `S3_SECRET_ACCESS_KEY` is **write-only** in the admin UI — it is never echoed back; leave the field blank when saving to keep the stored value.

| Variable               | Description                             | Default     |
| ---------------------- | --------------------------------------- | ----------- |
| `STORAGE_BACKEND`      | `local` or `s3`                         | `local`     |
| `S3_BUCKET`            | S3-compatible bucket name               | _(unset)_   |
| `S3_REGION`            | S3 region                               | `us-east-1` |
| `S3_ENDPOINT_URL`      | Custom S3 endpoint (R2, MinIO)          | _(unset)_   |
| `S3_ACCESS_KEY_ID`     | S3 access key                           | _(unset)_   |
| `S3_SECRET_ACCESS_KEY` | S3 secret key (write-only)              | _(unset)_   |
| `S3_PREFIX`            | Object key prefix                       | _(unset)_   |
| `S3_PUBLIC_URL`        | Public CDN URL for direct media serving | _(unset)_   |

## Performance

| Variable    | Description                                          | Default |
| ----------- | ---------------------------------------------------- | ------- |
| `STATELESS` | Reload content and settings from DB on every request | `false` |

## Observability (optional)

| Variable                    | Description                          | Default     |
| --------------------------- | ------------------------------------ | ----------- |
| `OTEL_RESOURCE_ATTRIBUTES`  | OpenTelemetry resource attributes    | _(unset)_   |
| `OTEL_EXPORTER_OTLP_ENDPOINT` | OTLP collector endpoint            | _(unset)_   |
| `OTEL_EXPORTER_OTLP_INSECURE` | Allow insecure OTLP                | _(unset)_   |
| `OTEL_EXPORTER_OTLP_PROTOCOL` | OTLP protocol (`grpc`/`http`)      | _(unset)_   |
| `OTEL_METRICS_EXPORTER`     | Metrics exporter (`none` to disable) | _(unset)_   |