# CSS Styling

Garden CMS separates CSS into three layers, applied in this order:

1. **Admin CSS** — Pico CSS classless + a small `admin.css` layer. Used by `/admin/*`. Not configurable.
2. **Theme CSS** — each active theme defines its own base template and CSS. Themes ship Pico classless by default but can ship *anything* (UnoCSS, Tailwind, hand-rolled CSS). The active theme's `{% block head %}` and `<style>` block render after the Site Head content.
3. **Site Head CSS** — classless frameworks or extra head HTML injected via **Settings → Site Head**. Renders *before* the theme's own head block.

## Where the CSS engine lives

The **active theme** owns its own base CSS engine. Mycelium uses Pico classless + custom tokens. Sprig uses UnoCSS runtime. A theme that wants Tailwind Play CDN loads it itself. Themes are not required to be classless — they can be utility-first, hand-rolled, or whatever.

The **Site Head** setting is for *additional* head injections layered on top of whatever the active theme ships: an analytics snippet, a custom favicon, an extra stylesheet, an inline `<style>` block, a `<script>` for tracking. It's not the place to install a theme's base CSS engine — that's a theme concern.

## Classless CSS frameworks (via Site Head dropdown)

The admin includes presets for 45 classless CSS frameworks. Go to **Settings → Site Head** and pick one from the dropdown above the textarea. The framework is applied to the public site on top of whatever the active theme already ships.

Available frameworks include Pico, Simple, MVP, Water, Sakura, Marx, new.css, Bamboo, Bolt, and many more. Each framework styles standard HTML elements without requiring CSS classes.

## Custom CSS

### Via theme CSS

Each theme has a CSS field. This CSS is injected as a `<style>` block in the page `<head>`. Use it for theme-specific styling. The two seeded themes — Mycelium and Sprig — show the two main patterns:

- **Mycelium** ships Pico classless + a custom CSS override layer. The template body is classless; the CSS file is a Pico-token override.
- **Sprig** ships UnoCSS runtime. The template body uses utility classes (`flex`, `max-w-5xl`, `bg-white/80`); the CSS file only contains structural defaults that should apply regardless of utility usage.

### Via Site Head

The **Site Head** textarea in **Settings** accepts arbitrary HTML injected into `<head>` on the public site. Use it for:

- External stylesheet `<link>` tags
- Inline `<style>` blocks
- `<script>` tags for analytics, theme toggles, etc.
- `<meta>` tags

**Do not** paste utility-first CSS engine `<script>` tags here. They should live in the active theme's `{% block head %}` so they always render with that theme.

### Combining approaches

If you ship a classless framework via Site Head, it stacks on top of whatever the active theme provides. The theme's own `{% block head %}` and `<style>` block render after the Site Head content, so the theme always wins specificity ties.

## Dark mode

The default theme (Mycelium) includes a light/dark mode toggle using Pico CSS's `data-theme` attribute. It reads the user's system preference on first visit and saves the choice to `localStorage`.

Themes that use Pico CSS or other frameworks with dark mode support can implement similar behavior by setting `data-theme` on the `<html>` element.

## Updating a seeded theme's template

Themes are seeded into the database on first boot. Subsequent edits to the `db/connection.py` constants don't propagate to existing databases — use `scripts/refresh_themes.py` to re-seed Sprig and Mycelium in place without changing which is active. This is intended for development; production themes are managed in the admin.

## Admin CSS

The admin interface uses Pico CSS (classless variant) and is unaffected by public theme CSS. Admin-specific styles are set via the `admin_head` block in `layout/base.html`.
