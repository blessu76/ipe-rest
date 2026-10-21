# Adding a journal post (weekly) — checklist

1. `mkdir journal/YYYY-MM-DD-slug && cp scripts/journal-post-template.html journal/YYYY-MM-DD-slug/index.html`
2. Replace every `YYYY-MM-DD`, `slug`, `TODO` (title EN/KO, description, excerpt EN/KO, keywords, abstract, EN+KO prose).
3. JSON-LD `about`: keep the ipe() Organization; list the albums/tracks/terms the post discusses
   (`MusicAlbum`, `MusicRecording`, `DefinedTerm`) and delete the sample entries that don't apply.
   Sources you quote → add `"citation": [{"@type":"CreativeWork","name":"…","url":"https://…"}]`.
   Author stays the Organization — no personal names, no e-mail addresses.
4. Image: default is `/og-image.png` (1200×630). A post-specific image → put it under `/journal/<slug>/` and set
   `image.url/width/height` + `og:image`/`twitter:image`.
5. `python3 scripts/journal_sync.py` — validates the post (canonical, hreflang, `<article>`, 2×h1, JSON-LD) and
   regenerates `journal/index.html` (cards + Blog/ItemList JSON-LD), `sitemap.xml`, `llms.txt` and the post's `wordCount`.
6. `python3 -m unittest discover tests` must be green.
7. Bump `CACHE` in `sw.js` (and `?v=` if css/js changed); check 375 px / 320 px.
8. Edited a post later? set `dateModified` in its JSON-LD, then rerun step 5 (sitemap `lastmod` follows).
9. After publishing (deployed to GitHub Pages): `python3 scripts/indexnow.py` — notifies IndexNow (Bing, Naver, Yandex…) of every sitemap URL (`--dry-run` to preview; or pass specific URLs). Key file: `c26cb51665a3463fe37863c316dc0080.txt` (public).

## Translations (12 languages: en ko ja zh es fr de pt ru ar hi id)
- Original (EN+KO in one file) stays at `/journal/<slug>/`. The 10 others are single-language static pages **generated** at
  `/journal/<lang>/<slug>/` (list: `/journal/<lang>/`) — never edit `journal/<lang>/` by hand.
- Source per post+language: `scripts/journal_i18n/<slug>/<lang>.json` (`title, description, abstract, excerpt, h1_html, body`; optional `keywords`, `dateModified`).
  UI strings per language: `scripts/journal_i18n/ui.json` (already filled for all 10).
- Post HTML needs the `<!-- journal:i18n:start/end -->` (hreflang + og:locale) and `<!-- journal:langnav:start/end -->` markers (in the template).
- `python3 scripts/journal_sync.py` generates translated pages/lists, hreflang + og:locale, `workTranslation`/`translationOfWork`, sitemap (per-language `<url>` + hreflang cluster) and llms.txt. Translated pages carry an "AI translation" note + link to the original.
- Machine translations are drafts: `ai_label`/`ai_text` in ui.json must stay. Missing languages are simply not listed (no empty hreflang).
