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


def posts():
    return sorted(d for d in (ROOT / "journal").iterdir() if journal_sync.DIR_RE.match(d.name))


class JournalGeo(unittest.TestCase):
    def test_in_sync_and_valid(self):
        writes, errors = journal_sync.build(ROOT)
        self.assertEqual(errors, [])
        stale = [str(p) for p, t in writes.items() if p.read_text(encoding="utf-8") != t]
        self.assertEqual(stale, [], "run: python3 scripts/journal_sync.py")

    def test_post_json_ld(self):
        for d in posts():
            src = (d / "index.html").read_text(encoding="utf-8")
            blobs = [json.loads(b) for b in LD.findall(src)]
            bp = next(b for b in blobs if b["@type"] == "BlogPosting")
            for k in ("image", "wordCount", "keywords", "inLanguage", "about", "datePublished", "dateModified"):
                self.assertTrue(bp.get(k), k)
            self.assertTrue(bp["image"]["url"].startswith("https://"))
            self.assertEqual(bp["author"]["@type"], "Organization")
            self.assertTrue(any(a.get("@type") == "Organization" for a in bp["about"]))
            self.assertIn("BreadcrumbList", [b["@type"] for b in blobs])
            self.assertNotIn("Davy", json.dumps(bp))

    def test_list_page_has_blog_and_itemlist(self):
        src = (ROOT / "journal" / "index.html").read_text(encoding="utf-8")
        graph = json.loads(LD.findall(src)[0])["@graph"]
        types = {g["@type"]: g for g in graph}
        self.assertEqual(set(types), {"Blog", "ItemList"})
        self.assertEqual(types["ItemList"]["numberOfItems"], len(posts()))

    def test_sitemap_lists_every_post_with_lastmod_hreflang_image(self):
        root = ET.parse(ROOT / "sitemap.xml").getroot()
        urls = {u.find(SM + "loc").text: u for u in root.findall(SM + "url")}
        for d in posts():
            u = urls["https://ipe.rest/journal/%s/" % d.name]
            self.assertTrue(u.find(SM + "lastmod").text)
            self.assertGreaterEqual(len(u.findall("{http://www.w3.org/1999/xhtml}link")), 3)
            self.assertIsNotNone(u.find("{http://www.google.com/schemas/sitemap-image/1.1}image"))
        self.assertIn("https://ipe.rest/journal/", urls)

    def test_llms_and_robots(self):
        llms = (ROOT / "llms.txt").read_text(encoding="utf-8")
        for d in posts():
            self.assertIn("https://ipe.rest/journal/%s/" % d.name, llms)
        robots = (ROOT / "robots.txt").read_text()
        self.assertIn("Sitemap: https://ipe.rest/sitemap.xml", robots)
        self.assertNotRegex(robots, r"(?m)^Disallow:\s*/\s*$")

    def test_new_post_flows_through(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for name in ("journal", "sitemap.xml", "llms.txt", "og-image.png"):
                src = ROOT / name
                (shutil.copytree if src.is_dir() else shutil.copy)(src, root / name)
            old = posts()[0]
            new = root / "journal" / "2026-10-27-second-post"
            new.mkdir()
            s = (old / "index.html").read_text(encoding="utf-8")
            s = s.replace(old.name, new.name).replace("2026-10-20", "2026-10-27")
            (new / "index.html").write_text(s, encoding="utf-8")
            writes, errors = journal_sync.build(root)
            self.assertEqual(errors, [])
            self.assertIn("2026-10-27-second-post", writes[root / "sitemap.xml"])
            self.assertIn("2026-10-27-second-post", writes[root / "llms.txt"])
            self.assertIn("2026-10-27-second-post", writes[root / "journal" / "index.html"])

    def test_bad_post_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            shutil.copytree(ROOT / "journal", root / "journal")
            f = next((root / "journal").glob("2026-*/index.html"))
            f.write_text(f.read_text(encoding="utf-8").replace('hreflang="ko"', 'hreflang="xx"'), encoding="utf-8")
            shutil.copy(ROOT / "sitemap.xml", root / "sitemap.xml")
            shutil.copy(ROOT / "llms.txt", root / "llms.txt")
            shutil.copy(ROOT / "og-image.png", root / "og-image.png")
            _, errors = journal_sync.build(root)
            self.assertTrue(any("hreflang=ko" in e for e in errors))


class JournalValidation(unittest.TestCase):
    """Each check must fail on a broken copy of the real post (and pass on the real one)."""

    def build_with(self, edit):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            shutil.copytree(ROOT / "journal", root / "journal")
            for name in ("sitemap.xml", "llms.txt", "og-image.png", "icon-512.png"):
                shutil.copy(ROOT / name, root / name)
            f = next((root / "journal").glob("2026-*/index.html"))
            f.write_text(edit(f.read_text(encoding="utf-8")), encoding="utf-8")
            return journal_sync.build(root)[1]

    def test_unchanged_copy_is_valid(self):
        self.assertEqual(self.build_with(lambda s: s), [])

    def test_missing_image_file_is_rejected(self):
        og = "https://ipe.rest/og-image.png"
        errs = self.build_with(lambda s: s.replace(og, "https://ipe.rest/journal/nope/hero.png"))
        self.assertTrue(any("not in the repo" in e and "hero.png" in e for e in errs), errs)
        # each of the four places is checked on its own
        for label in ("BlogPosting.image.url", "BlogPosting.thumbnailUrl", "og:image", "twitter:image"):
            self.assertTrue(any(label in e for e in errs), (label, errs))
        # og:image alone
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

    def test_template_slug_folder_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for name in ("journal", "sitemap.xml", "llms.txt", "og-image.png", "icon-512.png"):
                src = ROOT / name
                (shutil.copytree if src.is_dir() else shutil.copy)(src, root / name)
            old = posts()[0]
            new = root / "journal" / "2026-10-20-slug"
            new.mkdir()
            s = (old / "index.html").read_text(encoding="utf-8").replace(old.name, new.name)
            (new / "index.html").write_text(s, encoding="utf-8")
            errs = journal_sync.build(root)[1]
            self.assertTrue(any("template slug" in e for e in errs), errs)

    def test_unclosed_h2_is_rejected(self):
        errs = self.build_with(lambda s: s.replace("</article>", "<p>Use <h2> for sections</p></article>", 1))
        self.assertTrue(any("<h2>" in e for e in errs), errs)

    def test_untouched_template_is_rejected_and_balanced(self):
        tpl = (ROOT / "scripts" / "journal-post-template.html").read_text(encoding="utf-8")
        self.assertEqual(len(re.findall(r"<h2[ >]", tpl)), len(re.findall(r"</h2>", tpl)))
        with tempfile.TemporaryDirectory() as tmp:
            d = Path(tmp) / "2026-10-30-new-post"
            d.mkdir()
            (d / "index.html").write_text(tpl.replace("YYYY-MM-DD-slug", d.name), encoding="utf-8")
            _, errs = journal_sync.load_post(d, ROOT)
            self.assertTrue(any("placeholder" in e for e in errs), errs)

    def test_list_entries_link_to_article_nodes(self):
        src = (ROOT / "journal" / "index.html").read_text(encoding="utf-8")
        blog = json.loads(LD.findall(src)[0])["@graph"][0]
        ids = {e["@id"] for e in blog["blogPost"]}
        for d in posts():
            self.assertIn("https://ipe.rest/journal/%s/#article" % d.name, ids)

    def test_llms_post_line_separator_is_not_em_dash(self):
        lines = [ln for ln in (ROOT / "llms.txt").read_text(encoding="utf-8").splitlines() if "/journal/20" in ln]
        self.assertTrue(lines)
        for ln in lines:
            self.assertRegex(ln, r"/journal/\d{4}-[^ ]+/ - \S")

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
        slug = posts()[0].name
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
            if "/journal/20" in url or url.endswith("/journal/") or re.search(r"/journal/[a-z]{2}/", url):
                self.assertEqual(set(self.hreflangs(src)), set(self.I.LANGS) | {"x-default"}, url)

    def test_html_lang_dir_and_og_locale(self):
        for url, (_, src) in self.pages.items():
            m = re.search(r"/journal/([a-z]{2})/", url)
            if not m:
                continue
            lang = m.group(1)
            self.assertIn('<html lang="%s" dir="%s">' % (lang, "rtl" if lang == "ar" else "ltr"), src, url)
            self.assertIn('<meta property="og:locale" content="%s">' % self.I.OG_LOCALE[lang], src, url)
            alts = re.findall(r'og:locale:alternate" content="([^"]+)"', src)
            self.assertEqual(set(alts), set(self.I.OG_LOCALE.values()) - {self.I.OG_LOCALE[lang]}, url)

    def test_translated_post_json_ld_and_ai_note(self):
        slug = posts()[0].name
        orig_url = "https://ipe.rest/journal/%s/" % slug
        orig_ld = next(b for b in self.lds(self.pages[orig_url][1]) if b["@type"] == "BlogPosting")
        listed = {w["inLanguage"]: w["@id"] for w in orig_ld["workTranslation"]}
        self.assertEqual(set(listed), set(self.I.TR_LANGS))
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
            self.assertIn('href="/journal/%s/"' % slug, src)  # link back to the original
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
            self.assertEqual(blog["translationOfWork"]["@id"], "https://ipe.rest/journal/#blog")
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
            for name in ("journal", "scripts", "sitemap.xml", "llms.txt", "og-image.png"):
                src = ROOT / name
                (shutil.copytree if src.is_dir() else shutil.copy)(src, root / name)
            ui = root / "scripts" / "journal_i18n" / "ui.json"
            data = json.loads(ui.read_text(encoding="utf-8"))
            del data["ja"]["ai_label"]
            ui.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
            _, errors = journal_sync.build(root)
            self.assertTrue(any("ui.json[ja] missing" in e and "ai_label" in e for e in errors), errors)
            # removing a translation source leaves its generated page behind -> reported as an orphan
            ui.write_text(json.dumps(json.loads((ROOT / "scripts" / "journal_i18n" / "ui.json").read_text(encoding="utf-8")), ensure_ascii=False), encoding="utf-8")
            (root / "scripts" / "journal_i18n" / posts()[0].name / "id.json").unlink()
            _, errors = journal_sync.build(root)
            self.assertTrue(any("orphan" in e and "/id/" in e.replace("\\", "/") for e in errors), errors)


if __name__ == "__main__":
    unittest.main()
