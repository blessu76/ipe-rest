# ipe.rest — studio umbrella home

Static site (home page generated from `scripts/home_src/index.html`; no bundler) deployed to GitHub Pages on push to `main`.
Design: "Quiet Systems" (2026-10-20) — white sheet, thin cobalt blueprint lines, numbered sections, Inter + JetBrains Mono (self-hosted in `fonts/`).

- i18n: 12 languages, one static page each: `/en/ /ko/ … /id/` (`ar` is RTL). Strings in `scripts/home_i18n/<lang>.json`; run `python3 scripts/home_sync.py` to regenerate `/<lang>/index.html`, the root `/index.html` (x-default language chooser), `sitemap.xml` and `llms.txt` — never edit those by hand. Old `?lang=xx` links are forwarded by script to `/xx/`.
- SEO/GEO: meta + hreflang + JSON-LD in `<head>`, `sitemap.xml`, `robots.txt`, `llms.txt`.
- Sub pages: `journal/`, `about/`, `contact/`, `privacy/` share `journal/journal.css` (EN/KO in one file, switched by `journal/journal.js`).
- New journal post: follow `scripts/README-journal.md` (template + `scripts/journal_sync.py` keeps list page, `sitemap.xml`, `llms.txt`, JSON-LD in sync).
- Cache: bump `?v=` in `index.html`, the sub pages and `CACHE` in `sw.js` together when assets change.
