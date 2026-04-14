# Collections

Collections define structured content types with custom fields, card templates for list views, and detail templates for individual items. Common examples include blogs, projects, portfolios, and event listings.

## Creating a collection

Go to **Collections** → **New collection**:

- **Name** — Display name (e.g. "Blog")
- **Slug** — URL prefix (e.g. `blog` serves items at `/blog/{item-slug}`)
- **Description** — Optional
- **Fields schema** — JSON array defining custom fields
- **Card template** — Jinja2 HTML for list/feed views
- **Detail template** — Jinja2 HTML for the full item page
- **Empty template** — HTML shown when the collection has no published items
- **Items per page** — Pagination size for feeds (default: 10)

## Fields schema

Define custom fields as a JSON array:

```json
[
  { "name": "summary", "type": "text", "required": true },
  { "name": "body", "type": "html", "required": true },
  { "name": "tags", "type": "text", "required": false }
]
```

These fields appear in the item editor and are stored as JSON. Access them in templates via `{{ item.field_name }}`.

## Card template

The card template renders each item in a feed. It receives an `item` object with all fields:

```jinja
<article>
  <h3><a href="/blog/{{ item.slug }}">{{ item.title }}</a></h3>
  <p>{{ item.summary }}</p>
</article>
```

## Detail template

The detail template renders a single item page. It also receives the `item` object:

```jinja
<article>
  <h1>{{ item.title }}</h1>
  {{ item.body }}
</article>
```

If no detail template is set, a default `<h1>` + body layout is used.

## Embedding feeds in pages

Use the `<CollectionFeed>` JinjaX component in any page body:

```jinja
<CollectionFeed slug="blog" />
```

This renders the collection's card template for each published item with HTMX-powered "Load more" pagination.

## Slug history

When you rename a collection item's slug, the old slug is recorded. Requests to the old URL automatically redirect (301) to the new one.

## Item ordering

Items are ordered by `sort_order`. Use the arrow buttons in the items list to reorder them. You can also mark items as **Featured** for use in custom template logic.
