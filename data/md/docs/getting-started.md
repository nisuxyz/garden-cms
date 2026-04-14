# Getting Started

This guide walks you through common tasks after [installation](/docs/installation).

## First login

Navigate to `/admin/login`. Enter the password set via the `ADMIN_PASSWORD` environment variable, or use the OAuth login button if OAuth is configured.

## Dashboard

The admin dashboard at `/admin` shows counts for pages, content blocks, and collections. The sidebar provides navigation to every section.

## Create a page

1. Go to **Pages** → **New page**
2. Enter a title and URL slug
3. Write the page body using Jinja2 template syntax
4. Check **Published** and optionally **Show in nav**
5. Save

The page body is a Jinja2 template. You can use content blocks (`{{ site.hero_headline }}`), media URLs (`{{ media_url("photo.jpg") }}`), and JinjaX components (`<CollectionFeed slug="blog" />`).

## Edit content blocks

Content blocks are global key/value pairs that you can reference in any template. Go to **Content Blocks** to create or edit them. Each block has a type:

- **text** — Plain text, rendered as-is
- **html** — HTML with Jinja2 support (can use `{{ media_url("file.jpg") }}`)
- **image** — Media file reference

Access any block in templates with `{{ site.key }}`.

## Add a collection item

1. Go to **Collections** and select a collection (e.g. Blog)
2. Click **New item**
3. Fill in the title, slug, and custom fields defined by the collection schema
4. Check **Published** and save

Collection items are served at `/{collection_slug}/{item_slug}` and rendered through the collection's detail template.

## Upload media

Go to **Media** → **Upload** to add images. Uploaded files are available via `{{ media_url("filename.jpg") }}` in templates and content blocks. The `<MediaImage>` JinjaX component provides a convenient shorthand:

```html
<MediaImage src="filename.jpg" alt="Description" />
```

## Change the theme

Go to **Themes** to view, edit, or create themes. The active theme wraps all public pages. Each theme consists of a Jinja2 base template and CSS. You can also set a per-page theme override in the page editor.
