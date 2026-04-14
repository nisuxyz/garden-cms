# Pages

Pages are the core content unit in Garden CMS. Each page has a Jinja2 template body, a URL slug, and optional navigation and publishing controls.

## Creating a page

In the admin, go to **Pages** → **New page**. Fill in:

- **Title** — Display title, also used in navigation and the HTML `<title>` tag
- **Slug** — URL path (e.g. `about` serves at `/about`)
- **Body** — Jinja2 template content (see [Templates](templates))
- **Meta description** — Optional, for SEO
- **Published** — Only published pages are served on the public site
- **Show in nav** — Include this page in the theme's navigation menu
- **Homepage** — Mark one page as the homepage (served at `/`)

## Template body

The body field is a full Jinja2 template. You have access to:

- `{{ site.key }}` — Content block values
- `{{ media_url("filename.jpg") }}` — Public media URLs
- `<CollectionFeed slug="blog" />` — Embedded collection feeds
- `<MediaImage src="file.jpg" alt="..." />` — Image component
- Standard Jinja2 syntax (loops, conditionals, filters)

## Navigation order

Pages marked **Show in nav** appear in the navigation menu rendered by the active theme. Use the arrow buttons on the pages list to reorder them. The homepage always resolves at `/` regardless of its slug.

## Per-page themes

Each page can optionally override the site's active theme. Select a theme in the page editor to use a different base template and CSS for that page. If no override is set, the active theme is used.

## Slug routing

Pages are resolved by slug at `/{slug}`. The routing priority is:

1. Exact page slug match
2. Collection item match (`{collection_slug}/{item_slug}`)
3. Slug history redirect (301)
4. Markdown mount match
5. 404
