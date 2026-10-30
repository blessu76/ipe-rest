# Adding a journal post (daily — one post a day, at a random time between 10:00 and 11:00 KST) — checklist

1. `cp scripts/journal-post-template.html scripts/journal_src/YYYY-MM-DD-slug.html` (a SOURCE — not served; the pages are generated). Set `ipe:original` (en|ko) to the language you wrote it in.
2. Replace every `YYYY-MM-DD`, `slug`, `TODO` (title EN/KO, description EN/KO, excerpt EN/KO, keywords, abstract EN/KO, EN+KO prose).
3. JSON-LD `about`: keep the ipe() Organization; list the albums/tracks/terms the post discusses
   (`MusicAlbum`, `MusicRecording`, `DefinedTerm`) and delete the sample entries that don't apply.
   Sources you quote → add `"citation": [{"@type":"CreativeWork","name":"…","url":"https://…"}]`.
   Author stays the Organization — no personal names, no e-mail addresses.
4. Image: default is `/og-image.png` (1200×630). A post-specific image → put it under `/journal/<slug>/` and set
   `image.url/width/height` + `og:image`/`twitter:image`.
5. `python3 scripts/journal_sync.py` — validates the source (canonical, `<article>`, 2×h1, JSON-LD, images, placeholders) and
   regenerates every `journal/**/index.html`, `sitemap.xml` and `llms.txt` (see below).
5b. `python3 scripts/home_sync.py` — **main-page journal cards**: the newest 3 posts (per language) (section `03 journal`) on `/<lang>/` are generated from the same sources; run it after every journal_sync (the test `test_generated_files_in_sync` fails if the cards are stale). A post is on the main page as soon as its page is.
6. `python3 -m unittest discover tests` must be green.
7. Bump `CACHE` in `sw.js` (and `?v=` if css/js changed); check 375 px / 320 px.
8. Edited a post later? set `dateModified` in the source JSON-LD, then rerun step 5 (sitemap `lastmod` follows).
9. The deploy workflow now runs `python3 scripts/indexnow.py --today` after each deploy (only URLs whose sitemap lastmod is today KST; failures never block the deploy). Manual: `python3 scripts/indexnow.py` — notifies IndexNow (Bing, Naver, Yandex…) of every sitemap URL (`--dry-run` to preview; or pass specific URLs). Key file: `c26cb51665a3463fe37863c316dc0080.txt` (public).


## URLs and languages (12: en ko ja zh es fr de pt ru ar hi id) — all equal, all static, never `?lang=`
- `/journal/<lang>/<slug>/` and list `/journal/<lang>/`. **Generated — never edit `journal/**/index.html` by hand.**
- en + ko come from the bilingual source. The other 10 come from `scripts/journal_i18n/<slug>/<lang>.json`
  (`title, description, abstract, excerpt, h1_html, body`; optional `keywords`, `dateModified`); UI strings per language: `scripts/journal_i18n/ui.json`.
- `/journal/<slug>/` and `/journal/` are generated **language-chooser shells** (language-less): `journal.js` sends visitors to their stored/browser language,
  crawlers without a language simply see the list. They must never compete with the language pages (Search Console picked the shell over `/journal/en/<slug>/`): canonical → `/journal/en/…`,
  hreflang x-default → `/journal/en/…` on **every** journal page, **not in the sitemap**, llms.txt links the `/en/` URL. **No `noindex`** on the shell (noindex + canonical to another URL = mixed signals). Tests: `JournalShellSeo`.
- Original = `ipe:original`: its page carries `workTranslation` (the other 11), the rest `translationOfWork` → original.
  The "AI translation" note appears only on the 10 machine-translated languages, never on EN/KO.
- A language without a translation JSON is simply absent (no empty page, no dangling hreflang). Machine drafts: keep `ai_label`/`ai_text` in ui.json.
- sitemap: every language page (12 per post and per list; no shells) with lastmod, 13 hreflang (x-default = en), image. llms.txt lists all languages.

## RSS feed (💡#126)

`journal_sync.py` also writes `journal/feed.xml` (RSS 2.0, English, posts with datePublished <= today KST, newest first; not in the sitemap). The slug `feed` is reserved. Every journal/home/info page carries `<link rel="alternate" type="application/rss+xml">`. A post dated in the future appears in the feed (and `--check` goes stale) on its day — rerun the sync then.
