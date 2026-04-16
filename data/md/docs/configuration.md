# Configuration

All configuration is done via environment variables. Settings with a default value are optional.

## Core

| Variable       | Description                                  | Default                                              |
| -------------- | -------------------------------------------- | ---------------------------------------------------- |
| `DATABASE_URL` | PostgreSQL connection string                 | `postgres://postgres:postgres@localhost:5432/garden` |
| `SECRET_KEY`   | Session cookie encryption key (min 16 chars) | `dev-secret-change-me`                               |
| `DEBUG`        | Enable debug mode                            | `false`                                              |

## Authentication

| Variable              | Description                         | Default                                           |
| --------------------- | ----------------------------------- | ------------------------------------------------- |
| `ADMIN_PASSWORD`      | Password for admin login            | _(unset, login disabled unless OAuth configured)_ |
| `OAUTH_CLIENT_ID`     | OAuth2/OIDC client ID               | _(unset)_                                         |
| `OAUTH_CLIENT_SECRET` | OAuth2/OIDC client secret           | _(unset)_                                         |
| `OAUTH_ISSUER_URL`    | OAuth provider issuer URL           | _(unset)_                                         |
| `OAUTH_REDIRECT_URI`  | OAuth callback URL                  | _(unset)_                                         |
| `OAUTH_ALLOWED_GROUP` | Restrict admin access to this group | _(unset, all authenticated users)_                |

## Storage

These can also be configured in **Settings** in the admin. Environment variables take effect as fallbacks when no database setting exists.

| Variable               | Description                             | Default   |
| ---------------------- | --------------------------------------- | --------- |
| `S3_BUCKET`            | S3-compatible bucket name               | _(unset)_ |
| `S3_REGION`            | S3 region                               | _(unset)_ |
| `S3_ENDPOINT_URL`      | Custom S3 endpoint (R2, MinIO)          | _(unset)_ |
| `S3_ACCESS_KEY_ID`     | S3 access key                           | _(unset)_ |
| `S3_SECRET_ACCESS_KEY` | S3 secret key                           | _(unset)_ |
| `S3_PREFIX`            | Object key prefix                       | _(unset)_ |
| `S3_PUBLIC_URL`        | Public CDN URL for direct media serving | _(unset)_ |

## Performance

| Variable    | Description                                          | Default |
| ----------- | ---------------------------------------------------- | ------- |
| `STATELESS` | Reload content and settings from DB on every request | `false` |
