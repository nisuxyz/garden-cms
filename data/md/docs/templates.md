# Templates

Garden CMS uses Jinja2 for all template rendering, with JinjaX for reusable components.

## Template context

Every template (page bodies, content blocks, collection templates) has access to these globals:

| Variable                 | Description                                                    |
| ------------------------ | -------------------------------------------------------------- |
| `site`                   | Dictionary of all content blocks, keyed by block key           |
| `media_url(filename)`    | Returns the public URL for an uploaded media file              |
| `fetch_collection(slug)` | Returns paginated collection data (items, has_more, next_page) |

## Jinja2 syntax

### Variables

```jinja
{{ site.hero_headline }}
{{ media_url("logo.png") }}
```

### Conditionals

```jinja
{% if site.hero_headline %}
  <h1>{{ site.hero_headline }}</h1>
{% endif %}
```

### Loops

```jinja
{% for item in nav_items %}
  <a href="{{ item.url }}">{{ item.title }}</a>
{% endfor %}
```

### Filters

Standard Jinja2 filters are available: `default`, `upper`, `lower`, `truncate`, `safe`, `escape`, etc.

## JinjaX components

JinjaX components are reusable template fragments defined as `.jinja` files in the `templates/` directory.

### CollectionFeed

Renders a paginated feed of collection items with HTMX-powered "Load more" pagination:

```jinja
<CollectionFeed slug="blog" />
```

This renders each published item using the collection's card template. When more items are available, a "Load more" button loads the next page via HTMX.

### MediaImage

Renders an image tag with the correct media URL:

```jinja
<MediaImage src="photo.jpg" alt="A photo" />
```

## Collection item templates

### Card template

Used in feeds. Receives `item` with all fields:

```jinja
<article>
  <h3><a href="/blog/{{ item.slug }}">{{ item.title }}</a></h3>
  <p>{{ item.summary }}</p>
</article>
```

### Detail template

Used for the full item page. Also receives `item`:

```jinja
<article>
  <h1>{{ item.title }}</h1>
  {{ item.body }}
</article>
```

## Theme base template

Theme templates extend `layout/base.html` and receive `title`, `content`, `nav_items`, `extra_head`, and `logo`. See [Themes](themes) for details.

## Content block rendering

HTML content blocks are rendered through Jinja2 before being stored in the `site` dictionary. This means you can use `{{ media_url("file.jpg") }}` inside HTML content blocks and it will resolve correctly.
