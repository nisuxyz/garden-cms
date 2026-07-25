# db/connection.py
"""
Database lifecycle management for Piccolo + Litestar.

Provides an async lifespan context-manager that opens/closes the
Piccolo connection pool and ensures seed data exists.
"""
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from litestar import Litestar
from piccolo.engine.postgres import PostgresEngine

from db.tables import Collection, ContentBlock, Page, SiteSettings, Theme


# ── Seed data ──────────────────────────────────────────────

# Mycelium — the default classless theme. Sits on top of Pico CSS
# and overrides a small set of design tokens (sage accent, Fraunces
# display, Inter body) plus a layout vocabulary (header, footer,
# hero). No utility classes required in the template.

_MYCELIUM_TEMPLATE = """\
{% extends "layout/base.html" %}
{% block head %}
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link
    rel="stylesheet"
    href="https://fonts.googleapis.com/css2?family=Fraunces:opsz,wght@9..144,500;9..144,600;9..144,700&family=Inter:wght@400;500;600&family=JetBrains+Mono:wght@400;500&display=swap"
  >
  <script>
    (function () {
      var saved = localStorage.getItem("theme");
      var prefersDark = window.matchMedia("(prefers-color-scheme: dark)").matches;
      var theme = saved === "light" || saved === "dark" ? saved : (prefersDark ? "dark" : "light");
      document.documentElement.setAttribute("data-theme", theme);
      document.addEventListener("DOMContentLoaded", function () {
        document.querySelectorAll("[data-theme-toggle]").forEach(function (btn) {
          btn.setAttribute("aria-pressed", theme === "dark" ? "true" : "false");
          btn.addEventListener("click", function () {
            var current = document.documentElement.getAttribute("data-theme");
            var next = current === "dark" ? "light" : "dark";
            document.documentElement.setAttribute("data-theme", next);
            localStorage.setItem("theme", next);
            btn.setAttribute("aria-pressed", next === "dark" ? "true" : "false");
          });
        });
      });
    })();
  </script>
  {{ extra_head }}
{% endblock %}
{% block body %}
<header class="myco-header">
  <a class="myco-brand" href="/">
    {% if logo %}<img src="{{ logo }}" alt="" />{% endif %}
    <span>{{ site.site_name | default('Mycelium', true) }}</span>
  </a>
  <nav class="myco-nav" aria-label="Primary">
    <ul>
      {% for item in nav_items %}
      <li><a href="{{ item.url }}">{{ item.title }}</a></li>
      {% endfor %}
    </ul>
  </nav>
  <button
    type="button"
    class="myco-theme-toggle"
    data-theme-toggle
    aria-label="Toggle color scheme"
    title="Toggle light/dark"
  ></button>
</header>

<main class="myco-main">
  {{ content }}
</main>

<footer class="myco-footer">
  <div class="myco-footer__inner">
    <section class="myco-footer__about">
      <strong class="myco-footer__brand">
        {{ site.site_name | default('Mycelium', true) }}
      </strong>
      <p class="myco-footer__tagline">
        {{ site.tagline | default('A small garden, tended daily.', true) }}
      </p>
    </section>
    <section>
      <h3>Pages</h3>
      <ul>
        {% for item in nav_items %}
        <li><a href="{{ item.url }}">{{ item.title }}</a></li>
        {% endfor %}
      </ul>
    </section>
    <section>
      <h3>Elsewhere</h3>
      <ul>
        <li><a href="/docs">Documentation</a></li>
        <li><a href="/admin">Admin</a></li>
      </ul>
    </section>
  </div>
  <div class="myco-footer__base">
    <small>
      Built with
      <a href="https://github.com/itsnisuxyz/garden-cms" target="_blank" rel="noopener">Garden CMS</a>.
    </small>
  </div>
</footer>
{% endblock %}
"""

_MYCELIUM_CSS = """\
/* Mycelium — calm classless theme with a sage accent,
   Fraunces display type, and a three-column footer.

   Sits on top of Pico CSS (loaded as a classless framework
   default via site_head). Defines Pico's design tokens plus
   a small layout vocabulary — no utility classes required. */

:root,
:root[data-theme="light"] {
  --myco-accent: #6a8262;
  --myco-accent-strong: #4f6650;
  --myco-ink: #2d3528;
  --myco-ink-soft: #5c6258;
  --myco-paper: #f7f4ee;
  --myco-line: rgba(45, 53, 40, 0.12);
  --myco-rule: rgba(45, 53, 40, 0.06);
  --myco-shadow: 0 1px 2px rgba(45, 53, 40, 0.04), 0 4px 12px rgba(45, 53, 40, 0.06);

  --pico-primary: var(--myco-accent);
  --pico-primary-background: var(--myco-accent);
  --pico-primary-hover: var(--myco-accent-strong);
  --pico-primary-border: var(--myco-accent);
  --pico-primary-inverse: #ffffff;
  --pico-primary-focus: rgba(106, 130, 98, 0.3);
  --pico-primary-underline: rgba(106, 130, 98, 0.5);
  --pico-secondary: #9c8265;
  --pico-secondary-background: #9c8265;
  --pico-secondary-hover: #83694e;
  --pico-form-element-active-border-color: var(--myco-accent);
  --pico-form-element-focus-color: var(--pico-primary-focus);
  --pico-card-background-color: #ffffff;
  --pico-card-border-color: var(--myco-line);
  --pico-card-sectioning-background-color: rgba(106, 130, 98, 0.07);
  --pico-background-color: var(--myco-paper);
  --pico-color: var(--myco-ink);
  --pico-muted-color: var(--myco-ink-soft);
  --pico-muted-border-color: var(--myco-line);
  --pico-h1-color: var(--myco-ink);
  --pico-h2-color: var(--myco-ink);
  --pico-h3-color: var(--myco-ink);
  --pico-h4-color: var(--myco-ink);
  --pico-h5-color: var(--myco-ink);
  --pico-h6-color: var(--myco-ink);
  --pico-font-family-sans-serif: "Inter", system-ui, -apple-system, "Segoe UI", Roboto, sans-serif;
  --pico-font-family-serif: "Fraunces", Georgia, "Times New Roman", serif;
  --pico-font-family-monospace: "JetBrains Mono", ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
  --pico-font-family: var(--pico-font-family-sans-serif);
  --pico-font-weight: 400;
  --pico-line-height: 1.65;
  --pico-border-radius: 0.4rem;
  --pico-spacing: 1.1rem;
  --pico-typography-spacing-vertical: 1.4rem;
  --pico-block-spacing-vertical: 2rem;
  --pico-transition: 180ms cubic-bezier(0.16, 1, 0.3, 1);
}

:root[data-theme="dark"] {
  --myco-accent: #a8c2a3;
  --myco-accent-strong: #bcd0b8;
  --myco-ink: #ebe7df;
  --myco-ink-soft: #a8a9a3;
  --myco-paper: #1a1f1a;
  --myco-line: rgba(247, 244, 238, 0.12);
  --myco-rule: rgba(247, 244, 238, 0.06);
  --myco-shadow: 0 1px 2px rgba(0, 0, 0, 0.4), 0 4px 14px rgba(0, 0, 0, 0.3);

  --pico-primary: #a8c2a3;
  --pico-primary-background: #a8c2a3;
  --pico-primary-hover: #bcd0b8;
  --pico-primary-border: #a8c2a3;
  --pico-primary-focus: rgba(168, 194, 163, 0.3);
  --pico-secondary: #c7a98f;
  --pico-secondary-background: #c7a98f;
  --pico-secondary-hover: #d6b89e;
  --pico-card-background-color: #232823;
  --pico-card-border-color: var(--myco-line);
  --pico-card-sectioning-background-color: rgba(168, 194, 163, 0.07);
  --pico-background-color: var(--myco-paper);
  --pico-color: var(--myco-ink);
  --pico-muted-color: var(--myco-ink-soft);
  --pico-muted-border-color: var(--myco-line);
}

body {
  display: flex;
  flex-direction: column;
  min-height: 100vh;
  font-feature-settings: "ss01" on, "cv11" on;
}

main.myco-main {
  flex: 1;
  width: 100%;
  max-width: 64rem;
  margin: 0 auto;
  padding: 2.5rem 1.5rem 4rem;
}

h1, h2, h3, h4, h5, h6 {
  font-family: var(--pico-font-family-serif);
  font-weight: 600;
  letter-spacing: -0.012em;
  line-height: 1.2;
}
h1 { font-size: clamp(2.2rem, 4.5vw, 3.4rem); line-height: 1.08; }
h2 { font-size: clamp(1.5rem, 3vw, 2rem); margin-block-start: 2.5rem; }
h3 { font-size: 1.2rem; margin-block-start: 1.8rem; }

p, ul, ol { max-width: 65ch; }

code, pre {
  font-family: var(--pico-font-family-monospace);
  font-size: 0.92em;
}
pre {
  padding: 1rem 1.25rem;
  background: rgba(0, 0, 0, 0.04);
  border-radius: var(--pico-border-radius);
  overflow-x: auto;
}
:root[data-theme="dark"] pre {
  background: rgba(255, 255, 255, 0.04);
}

blockquote {
  border-inline-start: 3px solid var(--myco-accent);
  padding-inline-start: 1rem;
  color: var(--pico-muted-color);
  font-style: italic;
}

header.myco-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 2rem;
  max-width: 64rem;
  margin: 0 auto;
  padding: 1.5rem 1.5rem 0;
}
.myco-brand {
  display: inline-flex;
  align-items: center;
  gap: 0.55rem;
  text-decoration: none;
  color: inherit;
  font-family: var(--pico-font-family-serif);
  font-size: 1.25rem;
  font-weight: 600;
  letter-spacing: -0.01em;
}
.myco-brand img {
  width: 1.6rem;
  height: 1.6rem;
}
.myco-nav ul {
  display: flex;
  align-items: center;
  gap: 1.5rem;
  list-style: none;
  padding: 0;
  margin: 0;
}
.myco-nav a {
  text-decoration: none;
  color: var(--pico-color);
  font-size: 0.95rem;
  opacity: 0.75;
  transition: opacity 150ms, color 150ms;
}
.myco-nav a:hover,
.myco-nav a[aria-current="page"] {
  opacity: 1;
  color: var(--myco-accent);
}

.myco-theme-toggle {
  background: transparent;
  border: 1px solid var(--myco-line);
  width: 2rem;
  height: 2rem;
  padding: 0;
  border-radius: 999px;
  cursor: pointer;
  color: inherit;
  display: grid;
  place-items: center;
  font-size: 0;
  line-height: 1;
  transition: background var(--pico-transition), border-color var(--pico-transition);
}
.myco-theme-toggle:hover {
  background: var(--pico-card-background-color);
  border-color: var(--myco-accent);
}
:root[data-theme="light"] .myco-theme-toggle::before { content: "☽"; font-size: 0.95rem; }
:root[data-theme="dark"]  .myco-theme-toggle::before { content: "☀"; font-size: 0.95rem; }

article {
  border-radius: 0.6rem !important;
  transition: box-shadow var(--pico-transition), transform var(--pico-transition);
}
article:hover {
  box-shadow: var(--myco-shadow);
  transform: translateY(-1px);
}

.hero { padding: 3rem 0 2rem; }
.hero h1 {
  font-size: clamp(2.5rem, 6vw, 4.5rem);
  line-height: 1.02;
  margin-block-end: 1rem;
}
.hero p {
  font-size: 1.2rem;
  color: var(--pico-muted-color);
  max-width: 50ch;
}

.tag {
  display: inline-block;
  padding: 0.15rem 0.55rem;
  border-radius: 999px;
  background: var(--pico-secondary-background);
  color: var(--pico-secondary-inverse);
  font-family: var(--pico-font-family-monospace);
  font-size: 0.72rem;
  font-weight: 500;
  text-decoration: none;
}
.meta {
  color: var(--pico-muted-color);
  font-family: var(--pico-font-family-monospace);
  font-size: 0.8rem;
}

footer.myco-footer {
  margin-block-start: 5rem;
  border-block-start: 1px solid var(--myco-line);
  background: var(--pico-card-sectioning-background-color);
}
.myco-footer__inner {
  display: grid;
  gap: 2.5rem;
  grid-template-columns: 1.6fr 1fr 1fr;
  max-width: 64rem;
  margin: 0 auto;
  padding: 3rem 1.5rem 2rem;
}
.myco-footer h3 {
  font-size: 0.75rem;
  text-transform: uppercase;
  letter-spacing: 0.08em;
  color: var(--pico-muted-color);
  margin: 0 0 0.85rem;
  font-family: var(--pico-font-family-sans-serif);
  font-weight: 600;
}
.myco-footer ul {
  list-style: none;
  padding: 0;
  margin: 0;
  display: grid;
  gap: 0.45rem;
}
.myco-footer a {
  text-decoration: none;
  color: var(--pico-color);
  font-size: 0.95rem;
}
.myco-footer a:hover { color: var(--myco-accent); }
.myco-footer__about p {
  margin: 0;
  font-size: 0.95rem;
  color: var(--pico-muted-color);
}
.myco-footer__brand {
  display: block;
  font-family: var(--pico-font-family-serif);
  font-size: 1.6rem;
  margin-block-end: 0.4rem;
}
.myco-footer__base {
  border-block-start: 1px solid var(--myco-rule);
  text-align: center;
  padding: 1.25rem;
  color: var(--pico-muted-color);
}
.myco-footer__base a {
  color: inherit;
  text-decoration: underline;
  text-decoration-color: var(--myco-line);
}
.myco-footer__base a:hover { color: var(--myco-accent); }

@media (max-width: 768px) {
  header.myco-header { flex-wrap: wrap; gap: 0.75rem 1.5rem; padding-block-start: 1rem; }
  main.myco-main { padding: 2rem 1rem 3rem; }
  .myco-footer__inner {
    grid-template-columns: 1fr;
    gap: 1.5rem;
    padding: 2rem 1rem 1.5rem;
  }
}

@media (prefers-reduced-motion: reduce) {
  *, *::before, *::after {
    animation-duration: 0.001ms !important;
    transition-duration: 0.001ms !important;
  }
}
"""


# Sprig — a non-classless example theme. Most styling lives inline
# as UnoCSS utility classes; the CSS file only contains defaults
# that should apply regardless of utility usage (article cards,
# prose max-width, color-scheme).

_SPRIG_TEMPLATE = """\
{% extends "layout/base.html" %}
{# Sprig — utility-first theme.

   Most styling lives inline via UnoCSS utility classes
   (flex, grid-cols-2, px-6, etc.) that the runtime resolves
   on the fly. Only structural / semantic primitives live in CSS.

   The CSS engine (UnoCSS runtime) is loaded via this theme's
   Site Head field (Theme.site_head — see _SPRIG_SITE_HEAD), which
   the renderer injects into {{ extra_head }} below. To swap the
   engine, edit the theme's Site Head in the admin — no template
   edit needed. #}
{% block head %}
  <script>
    // Set the theme early. Sprig follows system preference by default and
    // remembers a manual choice. data-theme drives the Pico token overrides
    // in the theme CSS (so the emerald accent wins over pico.colors, which
    // otherwise out-specifies a bare :root); the .dark class drives the
    // utility dark: variants on the chrome.
    (function () {
      var saved = localStorage.getItem("theme");
      var prefersDark = window.matchMedia("(prefers-color-scheme: dark)").matches;
      var theme = saved === "light" || saved === "dark" ? saved : (prefersDark ? "dark" : "light");
      var root = document.documentElement;
      root.setAttribute("data-theme", theme);
      root.classList.toggle("dark", theme === "dark");
      document.addEventListener("DOMContentLoaded", function () {
        document.querySelectorAll("[data-theme-toggle]").forEach(function (btn) {
          btn.addEventListener("click", function () {
            var next = root.getAttribute("data-theme") === "dark" ? "light" : "dark";
            root.setAttribute("data-theme", next);
            root.classList.toggle("dark", next === "dark");
            localStorage.setItem("theme", next);
          });
        });
      });
    })();
  </script>
  {{ extra_head }}
{% endblock %}
{% block body %}
<header class="sticky top-0 z-10 backdrop-blur bg-white/80 dark:bg-slate-950/80 border-b border-slate-200/60 dark:border-slate-800/60">
  <div class="max-w-5xl mx-auto px-6 h-16 flex items-center justify-between">
    <a href="/" class="font-semibold text-lg tracking-tight text-slate-900 dark:text-slate-100 hover:text-emerald-600 dark:hover:text-emerald-400 transition">
      {{ site.site_name | default('Sprig', true) }}
    </a>
    <div class="flex items-center gap-6">
      <nav class="flex items-center gap-6 text-sm" aria-label="Primary">
        {% for item in nav_items %}
        <a href="{{ item.url }}" class="text-slate-600 dark:text-slate-300 hover:text-emerald-600 dark:hover:text-emerald-400 transition">
          {{ item.title }}
        </a>
        {% endfor %}
      </nav>
      <button type="button" class="sprig-toggle" data-theme-toggle
              aria-label="Toggle light/dark" title="Toggle light/dark">
        <span class="sprig-toggle__moon">&#9790;</span>
        <span class="sprig-toggle__sun">&#9728;</span>
      </button>
    </div>
  </div>
</header>

<main class="max-w-5xl mx-auto px-6 py-12">
  {{ content }}
</main>

<footer class="border-t border-slate-200/60 dark:border-slate-800/60 mt-20">
  <div class="max-w-5xl mx-auto px-6 py-10 flex flex-col sm:flex-row sm:justify-between gap-3 text-sm text-slate-500 dark:text-slate-400">
    <span>&copy; {{ site.site_name | default('Sprig', true) }}.</span>
    <span>
      Built with
      <a href="https://github.com/itsnisuxyz/garden-cms" target="_blank" rel="noopener" class="hover:text-emerald-600 dark:hover:text-emerald-400 transition">
        Garden CMS
      </a>.
    </span>
  </div>
</footer>
{% endblock %}
"""

_SPRIG_CSS = """\
/* Sprig — utility-first theme styled with UnoCSS runtime.

   This file provides:
   1. Pico token overrides so body content picks up the Sprig palette
      (slate + emerald, sans-serif, dark-friendly) instead of Pico's
      default green.
   2. Styles for the classless body elements that the body templates
      emit — h1-h6, p, pre, blockquote, table, article.
   3. A .hero class and a .sprig-grid class that the per-theme body
      template variants in this file can use.

   The UnoCSS runtime itself is loaded via this theme's Site Head
   field (_SPRIG_SITE_HEAD); utility classes (e.g. font-bold,
   rounded-lg, text-slate-900) appear in the rendered HTML only when
   UnoCSS has scanned the page. The base structural rules below are
   present whether or not UnoCSS is available. */

:root,
:root[data-theme="light"] {
  --pico-primary: #059669;
  --pico-primary-background: #059669;
  --pico-primary-hover: #047857;
  --pico-primary-border: #059669;
  --pico-primary-inverse: #ffffff;
  --pico-primary-focus: rgba(5, 150, 105, 0.25);
  --pico-primary-underline: rgba(5, 150, 105, 0.5);
  --pico-secondary: #475569;
  --pico-secondary-background: #475569;
  --pico-secondary-hover: #334155;
  --pico-form-element-active-border-color: #059669;
  --pico-form-element-focus-color: rgba(5, 150, 105, 0.25);
  --pico-card-background-color: #ffffff;
  --pico-card-border-color: #e2e8f0;
  --pico-card-sectioning-background-color: rgba(15, 23, 42, 0.04);
  --pico-background-color: #fafafa;
  --pico-color: #0f172a;
  --pico-muted-color: #475569;
  --pico-muted-border-color: #e2e8f0;
  --pico-h1-color: #0f172a;
  --pico-h2-color: #0f172a;
  --pico-h3-color: #0f172a;
  --pico-h4-color: #0f172a;
  --pico-h5-color: #0f172a;
  --pico-h6-color: #0f172a;
  --pico-font-family-sans-serif: "Inter", system-ui, -apple-system, "Segoe UI", Roboto,
                                 "Helvetica Neue", Arial, "Noto Sans", sans-serif;
  --pico-font-family-serif: "Inter", system-ui, sans-serif;  /* no serif in Sprig */
  --pico-font-family-monospace: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
  --pico-font-family: var(--pico-font-family-sans-serif);
  --pico-font-weight: 400;
  --pico-line-height: 1.7;
  --pico-border-radius: 0.5rem;
  --pico-spacing: 1rem;
  --pico-spacing-vertical: 1rem;
  --pico-spacing-horizontal: 1rem;
  --pico-typography-spacing-vertical: 1.4rem;
  --pico-block-spacing-vertical: 1.5rem;
  --pico-transition: 180ms cubic-bezier(0.16, 1, 0.3, 1);
  color-scheme: light;
}

:root[data-theme="dark"] {
  --pico-primary: #34d399;
  --pico-primary-background: #34d399;
  --pico-primary-hover: #6ee7b7;
  --pico-primary-border: #34d399;
  --pico-primary-focus: rgba(52, 211, 153, 0.3);
  --pico-primary-underline: rgba(52, 211, 153, 0.5);
  --pico-secondary: #94a3b8;
  --pico-card-background-color: #0f172a;
  --pico-card-border-color: #1e293b;
  --pico-card-sectioning-background-color: rgba(255, 255, 255, 0.04);
  --pico-background-color: #020617;
  --pico-color: #e2e8f0;
  --pico-muted-color: #94a3b8;
  --pico-muted-border-color: #1e293b;
  --pico-h1-color: #f1f5f9;
  --pico-h2-color: #f1f5f9;
  --pico-h3-color: #f1f5f9;
  color-scheme: dark;
}

html, body {
  margin: 0;
  padding: 0;
  font-family: var(--pico-font-family-sans-serif);
  font-feature-settings: "ss01" on, "cv11" on;
  -webkit-font-smoothing: antialiased;
  -moz-osx-font-smoothing: grayscale;
}

:root[data-theme="light"], :root:not([data-theme]) {
  background: var(--pico-background-color);
  color: var(--pico-color);
}
:root[data-theme="dark"] {
  background: var(--pico-background-color);
  color: var(--pico-color);
}

a { color: var(--pico-primary); }
a:hover { color: var(--pico-primary-hover); }

h1, h2, h3, h4, h5, h6 {
  font-family: var(--pico-font-family-sans-serif);
  font-weight: 700;
  letter-spacing: -0.018em;
  line-height: 1.2;
  color: var(--pico-h1-color);
}
h1 { font-size: clamp(2.25rem, 5vw, 3.25rem); line-height: 1.08; margin-block-end: 1rem; }
h2 { font-size: clamp(1.5rem, 3vw, 2rem); margin-block-start: 2.5rem; margin-block-end: 0.75rem; }
h3 { font-size: 1.2rem; margin-block-start: 1.8rem; margin-block-end: 0.5rem; }
h4, h5, h6 { font-size: 1rem; margin-block-start: 1.2rem; margin-block-end: 0.4rem; }

p, ul, ol { line-height: 1.7; }
p, ul, ol { max-width: 65ch; }

code, pre, kbd, samp {
  font-family: var(--pico-font-family-monospace);
  font-size: 0.92em;
}
code {
  background: rgba(15, 23, 42, 0.06);
  padding: 0.1rem 0.4rem;
  border-radius: 0.25rem;
  color: var(--pico-color);
}
:root[data-theme="dark"] code { background: rgba(255, 255, 255, 0.06); }
pre {
  padding: 1rem 1.25rem;
  border-radius: var(--pico-border-radius);
  background: #0f172a;
  color: #e2e8f0;
  overflow-x: auto;
  line-height: 1.5;
  border: 1px solid var(--pico-muted-border-color);
}
:root[data-theme="dark"] pre { background: #0b1220; }
pre code { background: transparent; padding: 0; color: inherit; }

blockquote {
  margin: 1.5rem 0;
  padding: 0.25rem 1.25rem;
  border-inline-start: 3px solid var(--pico-primary);
  color: var(--pico-muted-color);
  font-style: italic;
}

hr {
  border: 0;
  border-block-start: 1px solid var(--pico-muted-border-color);
  margin-block: 2rem;
}

table {
  display: block;
  width: 100%;
  overflow-x: auto;
  border-collapse: collapse;
  margin-block: 1.5rem;
}
th, td {
  padding: 0.6rem 0.9rem;
  border-block-end: 1px solid var(--pico-muted-border-color);
  text-align: start;
}
th {
  font-weight: 600;
  background: var(--pico-card-sectioning-background-color);
  color: var(--pico-color);
}

article {
  border: 1px solid var(--pico-muted-border-color);
  border-radius: 0.75rem;
  padding: 1.5rem;
  background: var(--pico-card-background-color);
  transition: box-shadow var(--pico-transition);
}
article:hover {
  box-shadow: 0 8px 24px rgba(15, 23, 42, 0.06);
}
:root[data-theme="dark"] article:hover {
  box-shadow: 0 8px 24px rgba(0, 0, 0, 0.3);
}

/* Hero block — used by the home page body variant */
.hero {
  padding: 3rem 0 2rem;
  max-width: 50rem;
}
.hero h1 {
  font-size: clamp(2.5rem, 6vw, 4rem);
  line-height: 1.04;
  letter-spacing: -0.025em;
  margin-block-end: 1rem;
}
.hero p {
  font-size: 1.2rem;
  color: var(--pico-muted-color);
  max-width: 50ch;
  margin-block-start: 0.75rem;
}

/* Grid for CollectionFeed output (used by the home page body variant) */
.sprig-grid {
  display: grid;
  gap: 1.25rem;
  grid-template-columns: repeat(auto-fit, minmax(16rem, 1fr));
  margin-block: 1.5rem;
}
.sprig-grid > article {
  margin: 0;
}

/* Theme toggle — styled here (not via utilities) so Pico's aggressive
   default <button> fill can't win. A class beats Pico's `button`
   element selector, and this theme <style> loads after Pico. */
.sprig-toggle {
  display: grid;
  place-items: center;
  width: 2.25rem;
  height: 2.25rem;
  margin: 0;
  padding: 0;
  border-radius: 999px;
  background: transparent;
  border: 1px solid var(--pico-muted-border-color);
  color: var(--pico-muted-color);
  cursor: pointer;
  line-height: 1;
  transition: color var(--pico-transition), border-color var(--pico-transition),
              background var(--pico-transition);
}
.sprig-toggle:hover {
  background: var(--pico-card-sectioning-background-color);
  border-color: var(--pico-primary);
  color: var(--pico-color);
}
.sprig-toggle:focus-visible {
  outline: 2px solid var(--pico-primary);
  outline-offset: 2px;
}
/* Icon swap keyed off data-theme (no UnoCSS dependency). */
.sprig-toggle__sun { display: none; }
.sprig-toggle__moon { display: inline; }
:root[data-theme="dark"] .sprig-toggle__sun { display: inline; }
:root[data-theme="dark"] .sprig-toggle__moon { display: none; }

@media (prefers-reduced-motion: reduce) {
  *, *::before, *::after {
    animation-duration: 0.001ms !important;
    transition-duration: 0.001ms !important;
  }
}
"""


# ── Per-theme Site Head (theme-specific <head> HTML) ────────
# Injected into the theme's own {% block head %} via {{ extra_head }},
# ahead of the theme's <style>. This is where a theme loads its CSS
# engine, fonts, or other theme-specific head assets. Kept out of the
# site-level Site Head setting so it travels with the theme.

_SPRIG_SITE_HEAD = (
    '<script type="module" '
    'src="https://cdn.jsdelivr.net/npm/@unocss/runtime/uno.global.js">'
    '</script>'
)

# Mycelium loads its fonts in its own base_template head block, so its
# Site Head field stays empty.
_MYCELIUM_SITE_HEAD = ""

# Base classless CSS framework each theme ships. Both use Pico as the
# base (Sprig layers UnoCSS on top via its Site Head, and its CSS
# overrides Pico's tokens).
_MYCELIUM_CSS_FRAMEWORK = "pico"
_SPRIG_CSS_FRAMEWORK = "pico"


# Shared docs styling for the classless (Pico-based) themes. The docs
# layout (data/md/docs/_layout.jinja) emits semantic .doc-shell markup;
# Mycelium and Sprig render it as a left sidebar using their Pico tokens,
# so it inherits each theme's accent automatically. Nightshade ships its
# own hand-rolled sidebar .doc-* rules inline instead.
_DOC_SIDEBAR_CSS = """
/* Docs (theme-driven .doc-shell markup) — left sidebar */
.doc-shell {
  display: grid;
  grid-template-columns: 15rem minmax(0, 1fr);
  gap: 3.5rem;
  align-items: start;
  max-width: 76rem;
  margin: 0 auto;
}
.doc-nav {
  position: sticky; top: 1.5rem; align-self: start;
  max-height: calc(100vh - 3rem); overflow-y: auto;
  padding-right: 0.5rem;
}
.doc-nav__title {
  display: block;
  font-size: 0.72rem; text-transform: uppercase; letter-spacing: 0.09em;
  color: var(--pico-muted-color); font-weight: 600;
  text-decoration: none; margin-bottom: 0.9rem;
}
.doc-nav ul { list-style: none; margin: 0; padding: 0; display: grid; gap: 0.1rem; }
.doc-nav li { max-width: none; }
.doc-nav a {
  display: block; text-decoration: none;
  color: var(--pico-muted-color);
  padding: 0.4rem 0.7rem; border-radius: 8px;
  border-left: 2px solid transparent; font-size: 0.92rem;
}
.doc-nav a:hover {
  color: var(--pico-color);
  background: var(--pico-card-sectioning-background-color);
}
.doc-nav a[aria-current="page"] {
  color: var(--pico-primary);
  background: var(--pico-card-sectioning-background-color);
  border-left-color: var(--pico-primary); font-weight: 600;
}
/* .doc-content is an <article>; neutralize the card/hover styling so the
   docs read as a flat document column, not a hovering card. */
.doc-content {
  min-width: 0; max-width: 46rem;
  background: none; border: 0; box-shadow: none;
  padding: 0; border-radius: 0; transition: none;
}
.doc-content:hover { box-shadow: none; transform: none; }
.doc-content > :first-child { margin-top: 0; }
.doc-crumbs { color: var(--pico-muted-color); font-size: 0.9rem; margin-block-end: 1.75rem; }
.doc-crumbs a { color: var(--pico-muted-color); text-decoration: underline; }
/* Mobile: sidebar collapses to a horizontal scroller on top. */
@media (max-width: 820px) {
  .doc-shell { grid-template-columns: 1fr; gap: 1.25rem; }
  .doc-nav {
    position: static; max-height: none; overflow: visible;
    padding: 0.5rem 0; border-block-end: 1px solid var(--pico-muted-border-color);
  }
  .doc-nav ul { grid-auto-flow: column; grid-auto-columns: max-content;
                overflow-x: auto; gap: 0.35rem; }
  .doc-nav a { border-left: 0; white-space: nowrap; }
  .doc-nav a[aria-current="page"] { border-left: 0; }
}
"""

_MYCELIUM_CSS = _MYCELIUM_CSS + _DOC_SIDEBAR_CSS
_SPRIG_CSS = _SPRIG_CSS + _DOC_SIDEBAR_CSS


# ── Nightshade ──────────────────────────────────────────────
# Dark-first, modern editorial theme. Hand-rolled CSS (no framework:
# css_framework="none"), a deep-berry red-purple accent, a sticky
# translucent top header, and a left sidebar for docs (via the
# theme-driven .doc-shell markup). Fonts load from its Site Head.

_NIGHTSHADE_CSS_FRAMEWORK = "none"

_NIGHTSHADE_SITE_HEAD = """\
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@500;600;700&family=Inter:wght@400;500;600&family=JetBrains+Mono:wght@400;500&display=swap">
"""

_NIGHTSHADE_TEMPLATE = """\
{% extends "layout/base.html" %}
{# Nightshade — dark-first editorial theme. The CSS engine is "none"
   (hand-rolled CSS); web fonts load from the theme Site Head. This
   template owns the page shell: a sticky top header, a centered
   content column, and a footer. The docs sidebar is produced by the
   theme-driven .doc-shell markup styled in this theme's CSS. #}
{% block head %}
  <script>
    (function () {
      // Dark-first: default to dark unless the visitor chose light.
      var saved = localStorage.getItem("theme");
      var theme = saved === "light" ? "light" : "dark";
      document.documentElement.setAttribute("data-theme", theme);
      document.addEventListener("DOMContentLoaded", function () {
        document.querySelectorAll("[data-theme-toggle]").forEach(function (btn) {
          var sync = function () {
            var cur = document.documentElement.getAttribute("data-theme");
            btn.setAttribute("aria-pressed", cur === "dark" ? "true" : "false");
          };
          sync();
          btn.addEventListener("click", function () {
            var cur = document.documentElement.getAttribute("data-theme");
            var next = cur === "dark" ? "light" : "dark";
            document.documentElement.setAttribute("data-theme", next);
            localStorage.setItem("theme", next);
            sync();
          });
        });
      });
    })();
  </script>
  {{ extra_head }}
{% endblock %}
{% block body %}
<a class="ns-skip" href="#ns-main">Skip to content</a>
<header class="ns-header">
  <div class="ns-header__inner">
    <a class="ns-brand" href="/">
      {% if logo %}<img src="{{ logo }}" alt="" />{% endif %}
      <span>{{ site.site_name | default('Nightshade', true) }}</span>
    </a>
    <nav class="ns-nav" aria-label="Primary">
      {% for item in nav_items %}
      <a href="{{ item.url }}">{{ item.title }}</a>
      {% endfor %}
    </nav>
    <button type="button" class="ns-toggle" data-theme-toggle
            aria-label="Toggle light/dark" title="Toggle light/dark"></button>
  </div>
</header>

<main class="ns-main" id="ns-main">
  {{ content }}
</main>

<footer class="ns-footer">
  <div class="ns-footer__inner">
    <span>&copy; {{ site.site_name | default('Nightshade', true) }}</span>
    <span>
      Built with
      <a href="https://github.com/itsnisuxyz/garden-cms" target="_blank" rel="noopener">Garden CMS</a>
    </span>
  </div>
</footer>
{% endblock %}
"""

_NIGHTSHADE_CSS = """\
/* Nightshade — dark-first editorial theme, hand-rolled (framework: none).
   Deep-berry red-purple accent, sticky translucent header, docs sidebar. */

:root, :root[data-theme="dark"] {
  --ns-bg: #0b0e14;
  --ns-surface: #12161f;
  --ns-surface-2: #171c26;
  --ns-border: rgba(255, 255, 255, 0.09);
  --ns-border-strong: rgba(255, 255, 255, 0.16);
  --ns-text: #e7e9ef;
  --ns-muted: #98a2b3;
  --ns-heading: #f6f7fb;
  --ns-accent: #e35aa6;
  --ns-accent-strong: #ef86c0;
  --ns-accent-dim: rgba(227, 90, 166, 0.16);
  --ns-accent-grad: linear-gradient(120deg, #e35aa6 0%, #b061e0 100%);
  --ns-code-bg: #0d1017;
  --ns-shadow: 0 1px 2px rgba(0,0,0,.4), 0 16px 40px rgba(0,0,0,.35);
  color-scheme: dark;
}

:root[data-theme="light"] {
  --ns-bg: #fbfbfd;
  --ns-surface: #ffffff;
  --ns-surface-2: #f5f5f8;
  --ns-border: rgba(15, 18, 26, 0.10);
  --ns-border-strong: rgba(15, 18, 26, 0.18);
  --ns-text: #2a2d34;
  --ns-muted: #5b6472;
  --ns-heading: #14161b;
  --ns-accent: #b52d78;
  --ns-accent-strong: #8f1f5e;
  --ns-accent-dim: rgba(181, 45, 120, 0.10);
  --ns-accent-grad: linear-gradient(120deg, #b52d78 0%, #7c3ab0 100%);
  --ns-code-bg: #f5f4f8;
  --ns-shadow: 0 1px 2px rgba(15,18,26,.06), 0 16px 40px rgba(15,18,26,.08);
  color-scheme: light;
}

* { box-sizing: border-box; }

html { scroll-behavior: smooth; }
@media (prefers-reduced-motion: reduce) { html { scroll-behavior: auto; } }

body {
  margin: 0;
  min-height: 100vh;
  display: flex;
  flex-direction: column;
  background: var(--ns-bg);
  color: var(--ns-text);
  font-family: "Inter", system-ui, -apple-system, "Segoe UI", Roboto, sans-serif;
  font-size: 1rem;
  line-height: 1.7;
  font-feature-settings: "cv05" on, "ss01" on;
  -webkit-font-smoothing: antialiased;
  -moz-osx-font-smoothing: grayscale;
}

::selection { background: var(--ns-accent-dim); }

:focus-visible {
  outline: 2px solid var(--ns-accent);
  outline-offset: 2px;
  border-radius: 4px;
}

a { color: var(--ns-accent); text-decoration: none; }
a:hover { color: var(--ns-accent-strong); }

h1, h2, h3, h4, h5, h6 {
  font-family: "Space Grotesk", "Inter", system-ui, sans-serif;
  color: var(--ns-heading);
  font-weight: 600;
  letter-spacing: -0.02em;
  line-height: 1.15;
  margin: 2.4rem 0 0.9rem;
}
h1 { font-size: clamp(2.2rem, 4.5vw, 3.1rem); margin-top: 0; }
h2 { font-size: clamp(1.5rem, 3vw, 1.95rem); }
h3 { font-size: 1.28rem; }
h4 { font-size: 1.05rem; }

p, ul, ol { margin: 0 0 1.1rem; }
p, li { max-width: 68ch; }

strong { color: var(--ns-heading); font-weight: 600; }

hr {
  border: 0;
  border-top: 1px solid var(--ns-border);
  margin: 2.5rem 0;
}

blockquote {
  margin: 1.6rem 0;
  padding: 0.4rem 1.25rem;
  border-left: 2px solid var(--ns-accent);
  color: var(--ns-muted);
  background: var(--ns-accent-dim);
  border-radius: 0 8px 8px 0;
}

code, kbd, samp, pre {
  font-family: "JetBrains Mono", ui-monospace, SFMono-Regular, Menlo, monospace;
  font-size: 0.9em;
}
:not(pre) > code {
  background: var(--ns-code-bg);
  border: 1px solid var(--ns-border);
  border-radius: 6px;
  padding: 0.12em 0.4em;
  color: var(--ns-heading);
}
pre {
  background: var(--ns-code-bg);
  border: 1px solid var(--ns-border);
  border-radius: 12px;
  padding: 1.1rem 1.25rem;
  overflow-x: auto;
  line-height: 1.6;
  margin: 1.4rem 0;
}
pre code { background: none; border: 0; padding: 0; }

table {
  width: 100%;
  border-collapse: collapse;
  margin: 1.6rem 0;
  font-size: 0.95rem;
  display: block;
  overflow-x: auto;
}
th, td {
  text-align: left;
  padding: 0.65rem 0.9rem;
  border-bottom: 1px solid var(--ns-border);
}
thead th {
  color: var(--ns-heading);
  font-weight: 600;
  border-bottom-color: var(--ns-border-strong);
}

img { max-width: 100%; height: auto; border-radius: 12px; }

/* Buttons / roled links (used by page bodies) */
[role="button"], button:not(.ns-toggle):not([data-theme-toggle]) {
  display: inline-flex;
  align-items: center;
  gap: 0.4rem;
  padding: 0.6rem 1.15rem;
  border-radius: 10px;
  border: 1px solid transparent;
  background: var(--ns-accent);
  color: #fff;
  font: inherit;
  font-weight: 500;
  cursor: pointer;
  transition: transform .15s ease, filter .15s ease;
}
[role="button"]:hover, button:not(.ns-toggle):not([data-theme-toggle]):hover {
  filter: brightness(1.08);
  transform: translateY(-1px);
  color: #fff;
}
[role="button"].secondary, [role="button"].outline {
  background: transparent;
  border-color: var(--ns-border-strong);
  color: var(--ns-text);
}

/* ── Skip link ─────────────────────────────────────────── */
.ns-skip {
  position: absolute; left: 0.75rem; top: 0.6rem; z-index: 60;
  transform: translateY(-160%);
  background: var(--ns-surface); color: var(--ns-text);
  border: 1px solid var(--ns-border-strong); border-radius: 8px;
  padding: 0.5rem 0.9rem; font-weight: 500;
  transition: transform .15s ease;
}
.ns-skip:focus { transform: translateY(0); }

/* ── Header ────────────────────────────────────────────── */
.ns-header {
  position: sticky; top: 0; z-index: 50;
  background: color-mix(in oklab, var(--ns-bg) 78%, transparent);
  backdrop-filter: saturate(140%) blur(12px);
  -webkit-backdrop-filter: saturate(140%) blur(12px);
  border-bottom: 1px solid var(--ns-border);
}
.ns-header__inner {
  max-width: 72rem; margin: 0 auto;
  height: 4rem; padding: 0 1.5rem;
  display: flex; align-items: center; gap: 1.5rem;
}
.ns-brand {
  display: inline-flex; align-items: center; gap: 0.55rem;
  font-family: "Space Grotesk", sans-serif;
  font-weight: 600; font-size: 1.1rem; letter-spacing: -0.01em;
  color: var(--ns-heading);
}
.ns-brand img { width: 1.6rem; height: 1.6rem; border-radius: 6px; }
.ns-nav {
  margin-left: auto;
  display: flex; align-items: center; gap: 1.6rem;
  font-size: 0.94rem;
}
.ns-nav a {
  color: var(--ns-muted); position: relative; padding: 0.2rem 0;
}
.ns-nav a:hover, .ns-nav a[aria-current="page"] { color: var(--ns-heading); }
.ns-nav a[aria-current="page"]::after {
  content: ""; position: absolute; left: 0; right: 0; bottom: -2px;
  height: 2px; border-radius: 2px; background: var(--ns-accent-grad);
}

.ns-toggle {
  width: 2.1rem; height: 2.1rem; flex: none;
  display: grid; place-items: center;
  border-radius: 999px; cursor: pointer;
  background: var(--ns-surface); color: var(--ns-muted);
  border: 1px solid var(--ns-border);
  transition: color .15s, border-color .15s, background .15s;
}
.ns-toggle:hover { color: var(--ns-heading); border-color: var(--ns-border-strong); }
.ns-toggle::before { font-size: 0.95rem; line-height: 1; }
:root[data-theme="dark"] .ns-toggle::before { content: "☀"; }
:root[data-theme="light"] .ns-toggle::before { content: "☾"; }

/* ── Main column ───────────────────────────────────────── */
.ns-main {
  flex: 1;
  width: 100%;
  max-width: 52rem;
  margin: 0 auto;
  padding: 3.5rem 1.5rem 5rem;
}

/* ── Hero (home variant, and the default .hero fallback) ── */
.ns-hero, .hero { padding: 1.5rem 0 2.5rem; }
.ns-hero h1, .hero h1 {
  font-size: clamp(2.6rem, 7vw, 4.4rem);
  line-height: 1.03; letter-spacing: -0.035em;
  background: var(--ns-accent-grad);
  -webkit-background-clip: text; background-clip: text;
  color: transparent;
  margin: 0 0 1rem;
}
.ns-hero p, .hero p { font-size: 1.28rem; color: var(--ns-muted); max-width: 46ch; margin: 0; }
.ns-lead { font-size: 1.12rem; color: var(--ns-muted); max-width: 60ch; }

/* ── Card grid (home variant) ─────────────────────────── */
.ns-grid {
  display: grid; gap: 1.1rem;
  grid-template-columns: repeat(auto-fill, minmax(17rem, 1fr));
  margin: 1.5rem 0 2rem;
}
article {
  background: var(--ns-surface);
  border: 1px solid var(--ns-border);
  border-radius: 14px;
  padding: 1.4rem;
  margin: 0 0 1.1rem;
  transition: border-color .18s ease, transform .18s ease, box-shadow .18s ease;
}
article:hover {
  border-color: var(--ns-border-strong);
  transform: translateY(-2px);
  box-shadow: var(--ns-shadow);
}
article h3 { margin-top: 0; }
article h3 a { color: var(--ns-heading); }
article h3 a:hover { color: var(--ns-accent); }
article .meta, article small { color: var(--ns-muted); font-size: 0.85rem; }
.ns-grid > article { margin: 0; }

/* ── Footer ────────────────────────────────────────────── */
.ns-footer {
  border-top: 1px solid var(--ns-border);
  background: var(--ns-surface);
}
.ns-footer__inner {
  max-width: 72rem; margin: 0 auto; padding: 2rem 1.5rem;
  display: flex; justify-content: space-between; flex-wrap: wrap; gap: 0.75rem;
  color: var(--ns-muted); font-size: 0.9rem;
}
.ns-footer a { color: var(--ns-muted); }
.ns-footer a:hover { color: var(--ns-accent); }

/* ── Docs: left sidebar (theme-driven .doc-shell markup) ── */
.ns-main:has(.doc-shell) { max-width: 76rem; }
.doc-shell {
  display: grid;
  grid-template-columns: 15rem minmax(0, 1fr);
  gap: 3.5rem;
  align-items: start;
}
.doc-nav {
  position: sticky; top: 5.5rem;
  align-self: start;
  max-height: calc(100vh - 7rem);
  overflow-y: auto;
  padding-right: 0.5rem;
}
.doc-nav__title {
  display: block;
  font-family: "Space Grotesk", sans-serif;
  font-size: 0.75rem; text-transform: uppercase; letter-spacing: 0.1em;
  color: var(--ns-muted); font-weight: 600;
  margin-bottom: 0.9rem;
}
.doc-nav ul { list-style: none; margin: 0; padding: 0; display: grid; gap: 0.15rem; }
.doc-nav li { max-width: none; }
.doc-nav a {
  display: block;
  padding: 0.4rem 0.7rem;
  border-radius: 8px;
  color: var(--ns-muted);
  font-size: 0.92rem;
  border-left: 2px solid transparent;
}
.doc-nav a:hover { color: var(--ns-heading); background: var(--ns-surface-2); }
.doc-nav a[aria-current="page"] {
  color: var(--ns-heading);
  background: var(--ns-accent-dim);
  border-left-color: var(--ns-accent);
  font-weight: 500;
}
/* .doc-content is an <article>; keep it flat (no card/hover). */
.doc-content {
  min-width: 0;
  background: none; border: 0; box-shadow: none;
  padding: 0; border-radius: 0; transition: none;
}
.doc-content:hover { box-shadow: none; transform: none; }
.doc-content > :first-child { margin-top: 0; }
.doc-crumbs { color: var(--ns-muted); font-size: 0.85rem; margin-bottom: 1.75rem; }
.doc-crumbs a { color: var(--ns-muted); }
.doc-crumbs strong { color: var(--ns-text); }

/* ── Responsive ────────────────────────────────────────── */
@media (max-width: 820px) {
  .doc-shell { grid-template-columns: 1fr; gap: 1.5rem; }
  .doc-nav {
    position: static; max-height: none; overflow: visible;
    padding: 0.75rem 0; border-bottom: 1px solid var(--ns-border);
  }
  .doc-nav ul { grid-auto-flow: column; grid-auto-columns: max-content;
                overflow-x: auto; gap: 0.4rem; }
  .doc-nav a { border-left: 0; white-space: nowrap; }
  .doc-nav a[aria-current="page"] { border-left: 0; }
}
@media (max-width: 640px) {
  .ns-header__inner { gap: 0.9rem; padding: 0 1rem; }
  .ns-nav { gap: 1rem; }
  .ns-main { padding: 2.5rem 1rem 3.5rem; }
}
"""

# Backwards-compat aliases.
_DEFAULT_THEME_TEMPLATE = _MYCELIUM_TEMPLATE
_DEFAULT_THEME_CSS = _MYCELIUM_CSS


_DEFAULT_CONTENT_BLOCKS = [
    ("hero_headline", "Hero Headline", "text", "Hello, I'm here."),
    ("hero_subtext", "Hero Subtext", "text", "Developer, maker, and curious human."),
    ("site_name", "Site Name", "text", "Mycelium"),
    ("tagline", "Site Tagline", "text", "A small garden, tended daily."),
    ("about", "About (Home)", "html", "I build things, explore ideas, and occasionally write about what I learn along the way."),
    ("resume.intro", "Resume Intro", "html", "Here's a snapshot of my professional journey so far."),
    ("resume.experience", "Resume Experience", "html", "<h2>Experience</h2>\n\n<p><em>Add your experience here.</em></p>"),
    ("resume.education", "Resume Education", "html", "<h2>Education</h2>\n\n<p><em>Add your education here.</em></p>"),
    ("resume.skills", "Resume Skills", "html", "<h2>Skills</h2>\n\n<p><em>Add your skills here.</em></p>"),
    ("contact.intro", "Contact Intro", "html", "Have a question or want to say hello?"),
]

# ``item.body`` holds trusted HTML authored in the admin, and the production
# Jinja env autoescapes — so it must be piped through ``| safe`` or it renders
# as visible escaped markup. ``item.data`` values are plain strings (unlike
# ContentBlock html values, which arrive pre-wrapped in ``Markup``).
# Everything else — title, summary, tags — is plain text and stays escaped.

_BLOG_CARD_TEMPLATE = """\
<article>
  <header>
    <h3><a href="/blog/{{ item.slug }}">{{ item.title }}</a></h3>
    <small class="meta">{{ item.created_at | dateformat }}</small>
  </header>
  <p>{{ item.summary }}</p>
  {%- set tags = item.tags | taglist %}
  {%- if tags %}
  <footer>{% for tag in tags %}<span class="tag">{{ tag }}</span>{% endfor %}</footer>
  {%- endif %}
</article>
"""

_BLOG_DETAIL_TEMPLATE = """\
<article>
  <h1>{{ item.title }}</h1>
  <small class="meta">{{ item.created_at | dateformat }}</small>
  <p>{{ item.summary }}</p>
  <hr>
  {{ item.body | safe }}
  {%- set tags = item.tags | taglist %}
  {%- if tags %}
  <footer>{% for tag in tags %}<span class="tag">{{ tag }}</span>{% endfor %}</footer>
  {%- endif %}
</article>
"""

_PROJECT_CARD_TEMPLATE = """\
<article>
  <header>
    <h3><a href="/projects/{{ item.slug }}">{{ item.title }}</a></h3>
  </header>
  <p>{{ item.summary }}</p>
  {%- set tags = item.tags | taglist %}
  {%- if tags %}
  <footer>{% for tag in tags %}<span class="tag">{{ tag }}</span>{% endfor %}</footer>
  {%- endif %}
</article>
"""

_PROJECT_DETAIL_TEMPLATE = """\
<article>
  <h1>{{ item.title }}</h1>
  <p>{{ item.summary }}</p>
  {%- if item.url or item.repo_url %}
  <p class="project-links">
    {%- if item.url %}
    <a href="{{ item.url }}" target="_blank" rel="noopener noreferrer">&#8599; live</a>
    {%- endif %}
    {%- if item.repo_url %}
    <a href="{{ item.repo_url }}" target="_blank" rel="noopener noreferrer">source &#8599;</a>
    {%- endif %}
  </p>
  {%- endif %}
  <hr>
  {{ item.body | safe }}
  {%- set tags = item.tags | taglist %}
  {%- if tags %}
  <footer>{% for tag in tags %}<span class="tag">{{ tag }}</span>{% endfor %}</footer>
  {%- endif %}
</article>
"""

_HOME_PAGE = """\
<div class="hero">
  <h1>{{ site.hero_headline }}</h1>
  <p>{{ site.hero_subtext }}</p>
</div>

<p>{{ site.about }}</p>

<h2>Recent Posts</h2>
<CollectionFeed slug="blog" limit=3 />

<h2>Featured Projects</h2>
<CollectionFeed slug="projects" limit=4 />
"""

_BLOG_PAGE = """\
<h1>Blog</h1>
<CollectionFeed slug="blog" />
"""

_PROJECTS_PAGE = """\
<h1>Projects</h1>
<CollectionFeed slug="projects" />
"""

_RESUME_PAGE = """\
<h1>Resume / CV</h1>
<p>{{ site["resume.intro"] }}</p>
{{ site["resume.experience"] }}
{{ site["resume.skills"] }}
"""

_CONTACT_PAGE = """\
<h1>Contact</h1>
<p>{{ site["contact.intro"] }}</p>

<p><em>A contact-form handler is not configured for this site.</em></p>
"""

# Generic status/error page. Rendered by cms.errors.render_status_page for
# any error response, with status_code / status_text / error / traceback
# in context. Not shown in nav; published so resolve_page() finds it.
_ERROR_PAGE = """\
<section class="hero" style="text-align:center">
  <h1>{{ status_code | default(404) }}</h1>
  <p>
    {% if status_code == 404 %}We couldn't find that page.
    {% elif status_code and status_code >= 500 %}Something went wrong on our end.
    {% else %}{{ status_text | default("Error") }}
    {% endif %}
  </p>
  <p><a href="/">← Back home</a></p>
</section>
{% if traceback %}
<pre style="max-width:60rem;margin:2rem auto;overflow:auto;text-align:left">{{ traceback }}</pre>
{% endif %}
"""


async def init_db() -> None:
    """Seed default CMS data if tables are empty.

    Each section checks independently so a partial previous seed
    (e.g. theme created but pages failed) is completed on next run.
    """

    # ── Themes ─────────────────────────────────────────────
    # Both Mycelium and Sprig ship as seeded alternatives. Mycelium
    # is the default active theme; Sprig is inactive and available
    # for one-click activation via /admin/themes.
    if await Theme.count() == 0:
        await Theme(
            name="Mycelium",
            slug="mycelium",
            base_template=_MYCELIUM_TEMPLATE,
            css=_MYCELIUM_CSS,
            css_framework=_MYCELIUM_CSS_FRAMEWORK,
            site_head=_MYCELIUM_SITE_HEAD,
            active=True,
        ).save()
        await Theme(
            name="Sprig",
            slug="sprig",
            base_template=_SPRIG_TEMPLATE,
            css=_SPRIG_CSS,
            css_framework=_SPRIG_CSS_FRAMEWORK,
            site_head=_SPRIG_SITE_HEAD,
            active=False,
        ).save()
        await Theme(
            name="Nightshade",
            slug="nightshade",
            base_template=_NIGHTSHADE_TEMPLATE,
            css=_NIGHTSHADE_CSS,
            css_framework=_NIGHTSHADE_CSS_FRAMEWORK,
            site_head=_NIGHTSHADE_SITE_HEAD,
            active=False,
        ).save()

    # ── Content Blocks ─────────────────────────────────────
    if await ContentBlock.count() == 0:
        for key, label, block_type, value in _DEFAULT_CONTENT_BLOCKS:
            await ContentBlock(
                key=key, label=label, block_type=block_type, value=value,
            ).save()

    # ── Pages ──────────────────────────────────────────────
    if await Page.count() == 0:
        pages = [
            ("Home", "home", _HOME_PAGE, True, True, 0),
            ("Blog", "blog", _BLOG_PAGE, False, True, 1),
            ("Projects", "projects", _PROJECTS_PAGE, False, True, 2),
            ("Resume", "resume", _RESUME_PAGE, False, True, 3),
            ("Contact", "contact", _CONTACT_PAGE, False, True, 4),
            # Generic status page — published so the error handler can
            # resolve it, hidden from nav.
            ("Error", "error", _ERROR_PAGE, False, False, 5),
        ]
        for title, slug, body, is_homepage, show_in_nav, nav_order in pages:
            await Page(
                title=title,
                slug=slug,
                body=body,
                is_homepage=is_homepage,
                show_in_nav=show_in_nav,
                nav_order=nav_order,
                published=True,
            ).save()

    # ── Collections ────────────────────────────────────────
    if await Collection.count() == 0:
        await Collection(
            name="Blog Posts",
            slug="blog",
            description="Blog posts and articles",
            fields_schema=[
                {"name": "summary", "type": "text", "required": True},
                {"name": "body", "type": "html", "required": True},
                {"name": "tags", "type": "list", "required": False},
            ],
            card_template=_BLOG_CARD_TEMPLATE,
            detail_template=_BLOG_DETAIL_TEMPLATE,
            items_per_page=10,
        ).save()

        await Collection(
            name="Projects",
            slug="projects",
            description="Portfolio projects",
            fields_schema=[
                {"name": "summary", "type": "text", "required": True},
                {"name": "body", "type": "html", "required": True},
                {"name": "tags", "type": "list", "required": False},
                {"name": "url", "type": "url", "required": False},
                {"name": "repo_url", "type": "url", "required": False},
            ],
            card_template=_PROJECT_CARD_TEMPLATE,
            detail_template=_PROJECT_DETAIL_TEMPLATE,
            items_per_page=12,
        ).save()

    # ── Settings ───────────────────────────────────────────
    if await SiteSettings.count() == 0:
        defaults = [
            ("storage_backend", "local"),
            ("s3_bucket", ""),
            ("s3_region", "us-east-1"),
            ("s3_endpoint_url", ""),
            ("s3_access_key_id", ""),
            ("s3_secret_access_key", ""),
            ("s3_prefix", ""),
            ("s3_public_url", ""),
            # Theme-independent extra <head> HTML (analytics, meta, fonts).
            # The base CSS framework now lives on each Theme, not here.
            ("site_head", ""),
            # Generic error/status page (slug); the seeded "error" Page.
            ("status_page", "error"),
        ]
        for key, value in defaults:
            await SiteSettings(key=key, value=value).save()


@asynccontextmanager
async def db_lifespan(app: Litestar) -> AsyncGenerator[None]:
    """Start the Piccolo connection pool on startup, close on shutdown."""
    from piccolo_conf import DB  # noqa: WPS433 — deferred to allow env loading

    engine: PostgresEngine = DB

    await engine.start_connection_pool(max_inactive_connection_lifetime=300)
    try:
        await init_db()
        # Initialise the storage backend from DB settings.
        from cms.storage import load_backend
        await load_backend()
        # Load ContentBlock cache into memory.
        from cms.site_context import load_site_dict
        await load_site_dict()
        yield
    finally:
        await engine.close_connection_pool()
