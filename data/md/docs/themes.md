# Themes

Themes control the visual presentation of all public pages. Each theme consists of a Jinja2 base template and CSS.

## Structure

A theme has four parts:

- **Name** — Display name in the admin
- **Slug** — Unique identifier
- **Base template** — Jinja2 template that wraps page content
- **CSS** — Injected as a `<style>` block in the page head
- **Active** — Only one theme can be active at a time

## Base template

The base template extends `layout/base.html` and defines the page shell. It receives these template variables:

| Variable     | Description                                        |
| ------------ | -------------------------------------------------- |
| `title`      | Page title                                         |
| `content`    | Rendered page body HTML (safe)                     |
| `nav_items`  | List of `{title, slug, url}` dicts for navigation  |
| `extra_head` | Theme CSS wrapped in `<style>` tags                |
| `logo`       | Public URL of the configured logo image, or `None` |

### Example

```jinja
{% extends "layout/base.html" %}
{% block head %}
  {{ extra_head }}
{% endblock %}
{% block body %}
<header>
  <nav>
    {% if logo %}<img src="{{ logo }}" alt="Logo" />{% endif %}
    <ul>
      {% for item in nav_items %}
        <li><a href="{{ item.url }}">{{ item.title }}</a></li>
      {% endfor %}
    </ul>
  </nav>
</header>
<main>
  {{ content }}
</main>
{% endblock %}
```

## CSS frameworks

Garden CMS includes presets for 48 classless CSS frameworks. Go to **Settings** → **Site Head** and select a framework from the dropdown. The framework's `<link>` tag is injected into the public site's `<head>`. You can also paste custom `<link>` or `<style>` tags directly.

## Per-page overrides

Each page can optionally use a different theme. Select a theme in the page editor to override the active theme for that page. This is useful for landing pages or special layouts.

## Favicon and logo

Go to **Settings** to select an uploaded media file as the site favicon or logo. The favicon is served at `/favicon.ico`. The logo URL is passed to the theme base template as the `logo` variable.
