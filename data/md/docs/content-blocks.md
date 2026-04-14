# Content Blocks

Content blocks are global key/value pairs accessible in every template. They let you manage text, HTML snippets, and image references from the admin without editing template files.

## Creating a content block

Go to **Content Blocks** in the admin. Click the form at the top to create a new block:

- **Key** — Unique identifier used in templates (e.g. `hero_headline`)
- **Label** — Human-readable name shown in the admin
- **Type** — `text`, `html`, or `image`
- **Value** — The content

## Block types

### Text

Plain text, rendered as-is. Use for headings, labels, short descriptions.

### HTML

HTML content with full Jinja2 support. You can use `{{ media_url("file.jpg") }}` inside HTML blocks to reference uploaded media. The HTML is rendered through the Jinja2 engine before being stored in the template context.

### Image

A media filename reference. Store just the filename; use `{{ media_url(site.key) }}` in templates to get the full URL.

## Using in templates

All content blocks are available under the `site` object:

```jinja
<h1>{{ site.hero_headline }}</h1>
<p>{{ site.hero_subtext }}</p>
{{ site.about }}
```

For keys with dots (e.g. `resume.experience`), use bracket notation:

```jinja
{{ site['resume.experience'] }}
```

## Caching

Content blocks are cached in memory at startup and refreshed whenever you save a block in the admin. In [stateless mode](deployment#stateless-mode), blocks are reloaded from the database on every request.
