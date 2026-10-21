import json
import re
import shutil
import sys
import tempfile
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
import journal_sync  # noqa: E402

LD = re.compile(r'<script type="application/ld\+json">\s*(.*?)\s*</script>', re.S)
SM = "{http://www.sitemaps.org/schemas/sitemap/0.9}"


SRC = ROOT / "scripts" / "journal_src"


def posts():
    """Post sources (the served pages are generated from them)."""
    return sorted(f for f in SRC.glob("*.html") if journal_sync.DIR_RE.match(f.stem))


def slug_of(f):
    return f.stem


def copy_site(root, names=("journal", "scripts", "sitemap.xml", "llms.txt", "og-image.png", "icon-512.png")):
    for name in names:
        src = ROOT / name
        (shutil.copytree if src.is_dir() else shutil.copy)(src, root / name)


class JournalGeo(unittest.TestCase):
    def test_in_sync_and_valid(self):
        writes, errors = journal_sync.build(ROOT)
        self.assertEqual(errors, [])
        stale = [str(p) for p, t in writes.items() if not p.exists() or p.read_text(encoding="utf-8") != t]
        self.assertEqual(stale, [], "run: python3 scripts/journal_sync.py")

    def test_post_json_ld_for_every_language(self):
        for f in posts():
            slug = slug_of(f)
            for lang in ("en", "ko", "ja", "ar"):
                src = (ROOT / "journal" / lang / slug / "index.html").read_text(encoding="utf-8")
                blobs = [json.loads(b) for b in LD.findall(src)]
                bp = next(b for b in blobs if b["@type"] == "BlogPosting")
                for k in ("image", "wordCount", "keywords", "inLanguage", "about", "datePublished", "dateModified", "abstract"):
                    self.assertTrue(bp.get(k), (lang, k))
                self.assertEqual(bp["inLanguage"], lang)  # single value
                self.assertTrue(bp["image"]["url"].startswith("https://"))
                self.assertEqual(bp["author"]["@type"], "Organization")
                self.assertTrue(any(a.get("@type") == "Organization" for a in bp["about"]))
                self.assertIn("BreadcrumbList", [b["@type"] for b in blobs])
                self.assertNotIn("Davy", json.dumps(bp))

    def test_original_vs_translation_relations_and_ai_note(self):
        for f in posts():
            slug = slug_of(f)
            orig = re.search(r'ipe:original" content="(\w+)"', f.read_text(encoding="utf-8")).group(1)
            self.assertIn(orig, ("en", "ko"))
            base = "https://ipe.rest/journal/%s/%s/"
            for lang in journal_sync.I18N.LANGS:
                src = (ROOT / "journal" / lang / slug / "index.html").read_text(encoding="utf-8")
                bp = next(json.loads(b) for b in LD.findall(src) if json.loads(b)["@type"] == "BlogPosting")
                if lang == orig:
                    self.assertEqual(len(bp["workTranslation"]), 11)
                    self.assertNotIn("translationOfWork", bp)
                else:
                    self.assertEqual(bp["translationOfWork"]["@id"], base % (orig, slug) + "#article")
                    self.assertNotIn("workTranslation", bp)
                # AI-translation note only on the 10 machine-translated languages (not on the reviewed EN/KO)
                self.assertEqual('class="ai-note"' in src, lang in journal_sync.I18N.TR_LANGS, lang)

    def test_list_pages_have_blog_and_itemlist(self):
        for lang in journal_sync.I18N.LANGS:
            src = (ROOT / "journal" / lang / "index.html").read_text(encoding="utf-8")
            graph = json.loads(LD.findall(src)[0])["@graph"]
            types = {g["@type"]: g for g in graph}
            self.assertEqual(set(types), {"Blog", "ItemList"})
            self.assertEqual(types["ItemList"]["numberOfItems"], len(posts()))
            self.assertEqual(types["Blog"]["inLanguage"], lang)
            ids = {e["@id"] for e in types["Blog"]["blogPost"]}
            for f in posts():
                self.assertIn("https://ipe.rest/journal/%s/%s/#article" % (lang, slug_of(f)), ids)

    def test_sitemap_has_every_language_page_with_13_hreflang_and_image(self):
        root = ET.parse(ROOT / "sitemap.xml").getroot()
        urls = {u.find(SM + "loc").text: u for u in root.findall(SM + "url")}
        X = "{http://www.w3.org/1999/xhtml}link"
        for f in posts():
            for lang in [None] + journal_sync.I18N.LANGS:
                u = urls[journal_sync.I18N.post_url(slug_of(f), lang)]
                self.assertTrue(u.find(SM + "lastmod").text)
                self.assertEqual(len(u.findall(X)), 13)
                self.assertIsNotNone(u.find("{http://www.google.com/schemas/sitemap-image/1.1}image"))
        for lang in [None] + journal_sync.I18N.LANGS:
            self.assertEqual(len(urls[journal_sync.I18N.list_url(lang)].findall(X)), 13)
        self.assertFalse([l for l in urls if "?" in l], "no ?lang= urls in the sitemap")

    def test_no_query_string_urls_anywhere(self):
        for f in list((ROOT / "journal").rglob("index.html")) + [ROOT / "llms.txt"]:
            self.assertNotIn("?lang=", f.read_text(encoding="utf-8"), f)
        self.assertFalse(re.findall(r'"https://ipe\.rest/journal/[^"]*\?', (ROOT / "sitemap.xml").read_text(encoding="utf-8")))

    def test_every_journal_page_has_header_language_select(self):
        pages = [ROOT / "journal" / "index.html"] + [ROOT / "journal" / l / "index.html" for l in journal_sync.I18N.LANGS]
        for f in posts():
            pages.append(ROOT / "journal" / slug_of(f) / "index.html")
            pages += [ROOT / "journal" / l / slug_of(f) / "index.html" for l in journal_sync.I18N.LANGS]
        for f in pages:
            src = f.read_text(encoding="utf-8")
            m = re.search(r'<header class="topbar">.*?<select class="lang" data-lang-select[^>]*>(.*?)</select>.*?</header>', src, re.S)
            self.assertIsNotNone(m, f)
            opts = re.findall(r'<option value="([^"]*)"([^>]*)>', m.group(1))
            real = [v for v, _ in opts if v]
            self.assertEqual(len(real), 12, f)
            for v in real:  # every option is an existing static page (no 404 / empty page)
                self.assertTrue((ROOT / v.lstrip("/") / "index.html").is_file(), (f, v))
            selected = [v for v, a in opts if "selected" in a and "disabled" not in a]
            if f.parent.name in journal_sync.I18N.LANGS or f.parent.parent.name in journal_sync.I18N.LANGS:
                lang = f.parent.name if f.parent.name in journal_sync.I18N.LANGS else f.parent.parent.name
                self.assertEqual(selected, [v for v in real if v.startswith("/journal/%s/" % lang)], f)
            else:  # x-default chooser: nothing preselected
                self.assertEqual(selected, [], f)
            self.assertNotIn("langlist", src)

    def test_info_pages_use_header_language_select(self):
        for name in ("about", "contact", "privacy"):
            src = (ROOT / name / "index.html").read_text(encoding="utf-8")
            self.assertIn('<select class="lang" data-lang-pick', src, name)
            self.assertEqual(re.findall(r'<option value="(\w+)"', src), ["en", "ko"], name)
            self.assertNotIn("<button type=\"button\" data-lang", src, name)
            self.assertIn("journal.css?v=%s" % journal_sync.I18N.VER_CSS, src, name)
            self.assertIn("journal.js?v=%s" % journal_sync.I18N.VER_JS, src, name)

    def test_llms_and_robots(self):
        llms = (ROOT / "llms.txt").read_text(encoding="utf-8")
        for f in posts():
            for lang in [None] + journal_sync.I18N.LANGS:
                self.assertIn(journal_sync.I18N.post_url(slug_of(f), lang), llms)
        robots = (ROOT / "robots.txt").read_text()
        self.assertIn("Sitemap: https://ipe.rest/sitemap.xml", robots)
        self.assertNotRegex(robots, r"(?m)^Disallow:\s*/\s*$")

    def test_new_post_flows_through(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            copy_site(root)
            old = posts()[0]
            new = root / "scripts" / "journal_src" / "2026-10-27-second-post.html"
            s = old.read_text(encoding="utf-8")
            s = s.replace(old.stem, new.stem).replace("2026-10-20", "2026-10-27")
            new.write_text(s, encoding="utf-8")
            writes, errors = journal_sync.build(root)
            self.assertEqual(errors, [])
            for lang in journal_sync.I18N.LANGS[:2]:  # en + ko come from the source itself
                self.assertIn(root / "journal" / lang / "2026-10-27-second-post" / "index.html", writes)
            self.assertIn(root / "journal" / "2026-10-27-second-post" / "index.html", writes)
            self.assertIn("2026-10-27-second-post", writes[root / "sitemap.xml"])
            self.assertIn("2026-10-27-second-post", writes[root / "llms.txt"])
            self.assertIn("2026-10-27-second-post", writes[root / "journal" / "en" / "index.html"])
            # the new post has no translation JSON yet -> only en/ko in its cluster, never an empty ja page
            self.assertNotIn(root / "journal" / "ja" / "2026-10-27-second-post" / "index.html", writes)

    def test_bad_post_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            copy_site(root)
            f = next((root / "scripts" / "journal_src").glob("2026-*.html"))
            f.write_text(f.read_text(encoding="utf-8").replace('<link rel="canonical" href="https://ipe.rest/', '<link rel="canonical" href="https://example.com/'), encoding="utf-8")
            _, errors = journal_sync.build(root)
            self.assertTrue(any("canonical" in e for e in errors), errors)


class JournalValidation(unittest.TestCase):
    """Each check must fail on a broken copy of the real post source (and pass on the real one)."""

    def build_with(self, edit):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            copy_site(root)
            f = next((root / "scripts" / "journal_src").glob("2026-*.html"))
            f.write_text(edit(f.read_text(encoding="utf-8")), encoding="utf-8")
            return journal_sync.build(root)[1]

    def test_unchanged_copy_is_valid(self):
        self.assertEqual(self.build_with(lambda s: s), [])

    def test_missing_image_file_is_rejected(self):
        og = "https://ipe.rest/og-image.png"
        errs = self.build_with(lambda s: s.replace(og, "https://ipe.rest/journal/nope/hero.png"))
        self.assertTrue(any("not in the repo" in e and "hero.png" in e for e in errs), errs)
        for label in ("BlogPosting.image.url", "BlogPosting.thumbnailUrl", "og:image", "twitter:image"):
            self.assertTrue(any(label in e for e in errs), (label, errs))
        errs = self.build_with(lambda s: s.replace('property="og:image" content="%s"' % og,
                                                   'property="og:image" content="https://ipe.rest/gone.png"'))
        self.assertTrue(any(e.endswith("gone.png") and "og:image" in e for e in errs), errs)

    def test_image_path_cannot_escape_root(self):
        errs = self.build_with(lambda s: s.replace("https://ipe.rest/og-image.png", "https://ipe.rest/../../etc/hosts"))
        self.assertTrue(any("not in the repo" in e for e in errs), errs)

    def test_other_domain_image_is_not_checked(self):
        self.assertEqual(self.build_with(lambda s: s.replace("https://ipe.rest/og-image.png", "https://cdn.example.com/a.png")), [])

    def test_todo_placeholder_is_rejected(self):
        for field in ("excerpt-en", "excerpt-ko"):
            errs = self.build_with(lambda s: re.sub(r'(<meta name="ipe:%s" content=")' % field, r"\1TODO ", s))
            self.assertTrue(any("placeholder" in e and "TODO" in e for e in errs), (field, errs))
        errs = self.build_with(lambda s: s.replace("</p>", " TODO fix this.</p>", 1))
        self.assertTrue(any("placeholder" in e for e in errs), errs)
        errs = self.build_with(lambda s: re.sub(r'("keywords": ")', r"\1TODO ", s))
        self.assertTrue(any("placeholder" in e for e in errs), errs)

    def test_date_placeholder_is_rejected(self):
        errs = self.build_with(lambda s: s.replace('"dateModified": "2026-10-20"', '"dateModified": "YYYY-MM-DD"'))
        self.assertTrue(any("YYYY-MM-DD" in e for e in errs), errs)
        errs = self.build_with(lambda s: s.replace('"dateModified": "2026-10-20"', '"dateModified": "2026-13-45"'))
        self.assertTrue(any("real YYYY-MM-DD date" in e for e in errs), errs)

    def test_original_language_and_ko_meta_are_required(self):
        errs = self.build_with(lambda s: re.sub(r'<meta name="ipe:original"[^>]*>\n', "", s))
        self.assertTrue(any("ipe:original" in e for e in errs), errs)
        errs = self.build_with(lambda s: re.sub(r'<meta name="ipe:description-ko"[^>]*>\n', "", s))
        self.assertTrue(any("ipe:description-ko" in e for e in errs), errs)

    def test_template_slug_file_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            copy_site(root)
            old = posts()[0]
            new = root / "scripts" / "journal_src" / "2026-10-20-slug.html"
            new.write_text(old.read_text(encoding="utf-8").replace(old.stem, new.stem), encoding="utf-8")
            errs = journal_sync.build(root)[1]
            self.assertTrue(any("template slug" in e for e in errs), errs)

    def test_unclosed_h2_is_rejected(self):
        errs = self.build_with(lambda s: s.replace("</article>", "<p>Use <h2> for sections</p></article>", 1))
        self.assertTrue(any("<h2>" in e for e in errs), errs)

    def test_untouched_template_is_rejected_and_balanced(self):
        tpl = (ROOT / "scripts" / "journal-post-template.html").read_text(encoding="utf-8")
        self.assertEqual(len(re.findall(r"<h2[ >]", tpl)), len(re.findall(r"</h2>", tpl)))
        with tempfile.TemporaryDirectory() as tmp:
            f = Path(tmp) / "2026-10-30-new-post.html"
            f.write_text(tpl.replace("YYYY-MM-DD-slug", f.stem), encoding="utf-8")
            _, errs = journal_sync.load_post(f, ROOT)
            self.assertTrue(any("placeholder" in e for e in errs), errs)


class JournalI18n(unittest.TestCase):
    """12-language structure: static per-language URLs, hreflang cluster reciprocity, JSON-LD translation links."""

    @classmethod
    def setUpClass(cls):
        import journal_i18n
        cls.I = journal_i18n
        cls.pages = {}  # url -> (path, src)
        j = ROOT / "journal"
        for f in j.rglob("index.html"):
            rel = f.relative_to(j).parent.as_posix()
            url = "https://ipe.rest/journal/" + (rel + "/" if rel != "." else "")
            cls.pages[url] = (f, f.read_text(encoding="utf-8"))

    def hreflangs(self, src):
        return dict(re.findall(r'<link rel="alternate" hreflang="([^"]+)" href="([^"]+)">', src))

    def lds(self, src):
        return [json.loads(b) for b in LD.findall(src)]

    def page_for(self, url):
        return self.pages.get(url.split("?")[0])

    def test_translations_exist_for_every_language(self):
        slug = slug_of(posts()[0])
        for l in self.I.TR_LANGS:
            self.assertIn("https://ipe.rest/journal/%s/%s/" % (l, slug), self.pages, l)
            self.assertIn("https://ipe.rest/journal/%s/" % l, self.pages, l)

    def test_every_json_ld_block_parses(self):
        for url, (_, src) in self.pages.items():
            self.assertTrue(self.lds(src), url)

    def test_hreflang_clusters_are_reciprocal_and_self_referencing(self):
        for url, (_, src) in self.pages.items():
            hl = self.hreflangs(src)
            canon = re.search(r'<link rel="canonical" href="([^"]+)"', src).group(1)
            self.assertEqual(canon, url)
            self.assertIn("x-default", hl, url)
            self.assertEqual(len(set(hl.values())), len(hl), "duplicate hreflang target " + url)
            self.assertIn(url, [h.split("?")[0] for h in hl.values()], "no self reference " + url)
            for lang, target in hl.items():
                other = self.page_for(target)
                self.assertIsNotNone(other, "hreflang %s -> %s is not a page" % (lang, target))
                self.assertEqual(self.hreflangs(other[1]), hl, "cluster of %s differs from %s" % (target, url))

    def test_hreflang_covers_all_twelve_languages(self):
        for url, (_, src) in self.pages.items():
            self.assertEqual(set(self.hreflangs(src)), set(self.I.LANGS) | {"x-default"}, url)

    def test_html_lang_dir_and_og_locale(self):
        for url, (_, src) in self.pages.items():
            m = re.search(r"/journal/([a-z]{2})/", url)
            if not m:
                self.assertIn("data-chooser", src, url)  # x-default pages are the language choosers
                continue
            lang = m.group(1)
            self.assertIn('<html lang="%s" dir="%s">' % (lang, "rtl" if lang == "ar" else "ltr"), src, url)
            self.assertIn('<meta property="og:locale" content="%s">' % self.I.OG_LOCALE[lang], src, url)
            alts = re.findall(r'og:locale:alternate" content="([^"]+)"', src)
            self.assertEqual(set(alts), set(self.I.OG_LOCALE.values()) - {self.I.OG_LOCALE[lang]}, url)

    def test_translated_post_json_ld_and_ai_note(self):
        slug = slug_of(posts()[0])
        orig_url = "https://ipe.rest/journal/%s/" % slug
        orig_ld = next(b for b in self.lds(self.pages["https://ipe.rest/journal/en/%s/" % slug][1]) if b["@type"] == "BlogPosting")
        listed = {w["inLanguage"]: w["@id"] for w in orig_ld["workTranslation"]}
        self.assertEqual(set(listed), set(self.I.LANGS) - {"en"})
        orig_url = "https://ipe.rest/journal/en/%s/" % slug
        for l in self.I.TR_LANGS:
            url = "https://ipe.rest/journal/%s/%s/" % (l, slug)
            src = self.pages[url][1]
            blobs = self.lds(src)
            bp = next(b for b in blobs if b["@type"] == "BlogPosting")
            self.assertEqual(bp["inLanguage"], l)
            self.assertEqual(bp["@id"], url + "#article")
            self.assertEqual(listed[l], bp["@id"])
            self.assertEqual(bp["translationOfWork"]["@id"], orig_url + "#article")
            for k in ("image", "wordCount", "keywords", "about", "datePublished", "dateModified", "abstract", "author", "publisher"):
                self.assertTrue(bp.get(k), (l, k))
            self.assertNotIn("workTranslation", bp)
            self.assertIn("BreadcrumbList", [b["@type"] for b in blobs])
            self.assertIn('class="ai-note"', src)
            self.assertIn('href="/journal/en/%s/" hreflang="en"' % slug, src)  # link back to the original
            self.assertEqual(len(re.findall(r"<h1[ >]", src)), 1)
            self.assertIn("© 2026 ipe() · idle", src)
            self.assertIn("ipe(); // be still", src)

    def test_translated_list_has_blog_and_itemlist(self):
        for l in self.I.TR_LANGS:
            src = self.pages["https://ipe.rest/journal/%s/" % l][1]
            graph = self.lds(src)[0]["@graph"]
            self.assertEqual({g["@type"] for g in graph}, {"Blog", "ItemList"})
            blog = next(g for g in graph if g["@type"] == "Blog")
            self.assertEqual(blog["inLanguage"], l)
            for it in next(g for g in graph if g["@type"] == "ItemList")["itemListElement"]:
                self.assertIsNotNone(self.page_for(it["url"]), it["url"])

    def test_sitemap_matches_html_hreflang(self):
        root = ET.parse(ROOT / "sitemap.xml").getroot()
        X = "{http://www.w3.org/1999/xhtml}link"
        seen = 0
        for u in root.findall(SM + "url"):
            loc = u.find(SM + "loc").text
            if not loc.startswith("https://ipe.rest/journal/"):
                continue
            seen += 1
            self.assertIn(loc, self.pages, loc)
            sm = {l.get("hreflang"): l.get("href") for l in u.findall(X)}
            self.assertEqual(sm, self.hreflangs(self.pages[loc][1]), loc)
            self.assertTrue(u.find(SM + "lastmod").text, loc)
        self.assertEqual(seen, len(self.pages))

    def test_llms_lists_every_translation(self):
        llms = (ROOT / "llms.txt").read_text(encoding="utf-8")
        for url in self.pages:
            self.assertIn(url, llms, url)

    def test_internal_links_resolve(self):
        for url, (_, src) in self.pages.items():
            for href in re.findall(r'<a [^>]*href="(/[^"#?]*)', src):
                f = ROOT / href.lstrip("/")
                self.assertTrue(f.is_dir() and (f / "index.html").exists() or f.is_file(), "%s -> %s" % (url, href))

    def test_asset_versions_match_service_worker(self):
        sw = (ROOT / "sw.js").read_text(encoding="utf-8")
        for url, (_, src) in self.pages.items():
            for asset in re.findall(r'(?:href|src)="(/journal/journal\.(?:css|js)\?v=\d+)"', src):
                self.assertIn("'%s'" % asset, sw, "%s uses %s not listed in sw.js CORE" % (url, asset))

    def test_missing_ui_strings_and_orphans_are_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            copy_site(root)
            ui = root / "scripts" / "journal_i18n" / "ui.json"
            data = json.loads(ui.read_text(encoding="utf-8"))
            del data["ja"]["ai_label"]
            ui.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
            _, errors = journal_sync.build(root)
            self.assertTrue(any("ui.json[ja] missing" in e and "ai_label" in e for e in errors), errors)
            # removing a translation source leaves its generated page behind -> reported as an orphan
            ui.write_text(json.dumps(json.loads((ROOT / "scripts" / "journal_i18n" / "ui.json").read_text(encoding="utf-8")), ensure_ascii=False), encoding="utf-8")
            (root / "scripts" / "journal_i18n" / slug_of(posts()[0]) / "id.json").unlink()
            _, errors = journal_sync.build(root)
            self.assertTrue(any("orphan" in e and "/id/" in e.replace("\\", "/") for e in errors), errors)


if __name__ == "__main__":
    unittest.main()
