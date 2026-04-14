# Media

Garden CMS provides image upload and management with pluggable storage backends.

## Uploading files

Go to **Media** in the admin and use the upload form. Accepted file types:

- JPEG, PNG, GIF, WebP, SVG
- Maximum file size: 10 MB

Files are assigned a UUID-prefixed filename to prevent collisions. The original filename is preserved in the database for display.

## Using media in templates

Reference uploaded files in any template or content block:

```jinja
<img src="{{ media_url("photo.jpg") }}" alt="A photo" />
```

Or use the `<MediaImage>` JinjaX component:

```jinja
<MediaImage src="photo.jpg" alt="A photo" />
```

In content block editors, click the image buttons next to media files to insert a snippet automatically.

## Storage backends

### Local disk (default)

Files are stored in `data/media/` and served directly by the application at `/media/{filename}`. No additional configuration required.

### S3-compatible

Store files in any S3-compatible object storage (AWS S3, Cloudflare R2, MinIO, etc.). Configure in **Settings** or via environment variables:

| Setting           | Env variable           | Description                          |
| ----------------- | ---------------------- | ------------------------------------ |
| Bucket            | `S3_BUCKET`            | Bucket name                          |
| Region            | `S3_REGION`            | AWS region                           |
| Endpoint URL      | `S3_ENDPOINT_URL`      | Custom endpoint (R2, MinIO, etc.)    |
| Access Key ID     | `S3_ACCESS_KEY_ID`     | IAM access key                       |
| Secret Access Key | `S3_SECRET_ACCESS_KEY` | IAM secret key                       |
| Key Prefix        | `S3_PREFIX`            | Path prefix for uploaded objects     |
| Public URL Base   | `S3_PUBLIC_URL`        | CDN/public origin for direct serving |

When a **Public URL Base** is set, media requests redirect to that origin instead of proxying through the application. This is recommended for production.

## Caching

Media responses include a one-year `Cache-Control` header (`public, max-age=31536000, immutable`) since filenames contain UUIDs and never collide.
