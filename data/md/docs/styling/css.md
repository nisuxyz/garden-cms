# CSS Styling

Garden CMS separates CSS into two layers: the **admin interface** uses Pico CSS and is not configurable, while the **public site** CSS is fully controlled by themes and the Site Head setting.

## Classless CSS frameworks

The admin includes presets for 48 classless CSS frameworks. Go to **Settings** and use the **Site Head** dropdown to insert one. The framework is applied to the public site only.

Available frameworks include Pico, Simple, MVP, Water, Sakura, Marx, new.css, Bamboo, Bolt, and many more. Each framework styles standard HTML elements without requiring CSS classes.

## Custom CSS

### Via theme CSS

Each theme has a CSS field. This CSS is injected as a `<style>` block in the page `<head>`. Use it for theme-specific styling.

### Via Site Head

The **Site Head** textarea in **Settings** accepts arbitrary HTML injected into `<head>` on the public site. Use it for:

- External stylesheet `<link>` tags
- Inline `<style>` blocks
- Meta tags or script includes

### Combining approaches

You can use a classless framework via Site Head for base styling and override specific elements in the theme CSS. The theme CSS loads after the Site Head content.

## Dark mode

The default theme (Mycelium) includes a light/dark mode toggle using Pico CSS's `data-theme` attribute. It reads the user's system preference on first visit and saves the choice to `localStorage`.

Themes that use Pico CSS or other frameworks with dark mode support can implement similar behavior by setting `data-theme` on the `<html>` element.

## Admin CSS

The admin interface uses Pico CSS (classless variant) and is unaffected by public theme CSS. Admin-specific styles are set via the `admin_head` block in `layout/base.html`.
