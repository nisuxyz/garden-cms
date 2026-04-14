# Markdown Mounts

Markdown mounts let you serve directories of `.md` files as themed pages with file-based routing. This is useful for documentation, changelogs, or any content that's easier to manage as flat files.

## Setup

1. Create a subdirectory under `data/md/` (e.g. `data/md/docs/`)
2. Add `.md` files to the directory. Subdirectories map to nested URL paths
3. Go to **Markdown** in the admin
4. Set a route slug for the directory (e.g. `docs`)
5. Save

## File-based routing

The directory structure maps directly to URL paths. Given this layout:

```
data/md/docs/
  index.md
  getting-started.md
  installation.md
  styling/
    css.md
```

With the slug set to `docs`, the following routes are created:

| File                 | URL                     |
| -------------------- | ----------------------- |
| `index.md`           | `/docs`                 |
| `getting-started.md` | `/docs/getting-started` |
| `installation.md`    | `/docs/installation`    |
| `styling/css.md`     | `/docs/styling/css`     |

## Page titles

The page title is extracted from the first `# heading` in the markdown file. If no heading is found, the filename is used (e.g. `getting-started.md` becomes "Getting Started").

## Markdown features

Garden CMS uses Python-Markdown with these extensions:

- **Fenced code blocks** — Triple-backtick code blocks with language hints
- **Tables** — Pipe-delimited tables
- **Table of contents** — Generates `id` attributes on headings

## Theme integration

Markdown pages are rendered through the active theme, just like CMS pages. They receive the same navigation, CSS, logo, and site head configuration.

## Route priority

Markdown mounts are checked after CMS pages, collection items, and slug redirects. If a CMS page has the same slug as a markdown route, the CMS page takes priority.
