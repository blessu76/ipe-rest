# ipe.rest — studio umbrella home

Static single-page site (`index.html`, no build step) deployed to GitHub Pages on push to `main`.
Design: "Quiet Systems" (2026-10-20) — white sheet, thin cobalt blueprint lines, numbered sections, Inter + JetBrains Mono (self-hosted in `fonts/`).

- i18n: 12 languages in the `I18N` object at the bottom of `index.html` (`?lang=xx`, `ar` is RTL).
- SEO/GEO: meta + hreflang + JSON-LD in `<head>`, `sitemap.xml`, `robots.txt`, `llms.txt`.
- Cache: bump `?v=` in `index.html` and `CACHE` in `sw.js` together when assets change.
