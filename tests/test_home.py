import json
import re
import sys
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
import home_sync  # noqa: E402

LANGS = home_sync.LANGS
LD = re.compile(r'<script type="application/ld\+json">\s*(.*?)\s*</script>', re.S)
SM = "{http://www.sitemaps.org/schemas/sitemap/0.9}"
X = "{http://www.w3.org/1999/xhtml}link"


def page(lang):
    return (ROOT / lang / "index.html").read_text(encoding="utf-8") if lang else (ROOT / "index.html").read_text(encoding="utf-8")


def hreflangs(src):
    return dict(re.findall(r'<link rel="alternate" hreflang="([^"]+)" href="([^"]+)">', src))


class HomePages(unittest.TestCase):
    def test_generated_files_in_sync(self):
        writes, errors = home_sync.build()
        self.assertEqual(errors, [])
        stale = [str(p) for p, t in writes.items() if not p.exists() or p.read_text(encoding="utf-8") != t]
        self.assertEqual(stale, [], "run: python3 scripts/home_sync.py")

    def test_every_language_page(self):
        want = dict(home_sync.cluster())
        for lang in LANGS:
            src = page(lang)
            self.assertIn('<html lang="%s" dir="%s">' % (lang, "rtl" if lang == "ar" else "ltr"), src)
            self.assertIn('<link rel="canonical" href="https://ipe.rest/%s/">' % lang, src)
            self.assertIn('<meta property="og:url" content="https://ipe.rest/%s/">' % lang, src)
            self.assertIn('<meta property="og:locale" content="%s">' % home_sync.OG_LOCALE[lang], src)
            self.assertEqual(src.count('property="og:locale:alternate"'), 11)
            self.assertEqual(hreflangs(src), want)  # all 12 + x-default, identical on every page (mutual)
            self.assertIn("G-XG4BH800J0", src)  # GA tag on every language page
            self.assertIn("/journal/%s/" % lang, src)
            self.assertNotIn('href="/journal/en/"', src) if lang != "en" else None
            self.assertIn("ipe() · idle", src)
            self.assertNotIn("?lang=", re.sub(r"<script>.*?</script>|<!--.*?-->", "", src, flags=re.S))

    def test_titles_and_descriptions_are_per_language(self):
        titles = set()
        for lang in LANGS:
            src = page(lang)
            t = re.search(r"<title>(.*?)</title>", src).group(1)
            titles.add(t)
            self.assertIn('content="%s"' % home_sync.esc(json.loads((ROOT / "scripts/home_i18n" / (lang + ".json")).read_text(encoding="utf-8"))["meta_desc"]), src)
            self.assertEqual(src.count('property="og:title" content="%s"' % home_sync.esc(t.replace("&amp;", "&"))), 1, lang)
        self.assertEqual(len(titles), 12)

    def test_json_ld_in_language(self):
        for lang in LANGS:
            blobs = [json.loads(b) for b in LD.findall(page(lang))]
            site = next(b for b in blobs if b["@type"] == "WebSite")
            self.assertEqual(site["url"], "https://ipe.rest/%s/" % lang)
            self.assertEqual(site["inLanguage"], lang)
            self.assertEqual('"FAQPage"' in page(lang), lang == "en")

    def test_root_is_chooser_with_query_forward(self):
        src = page(None)
        self.assertIn('<link rel="canonical" href="https://ipe.rest/">', src)
        self.assertEqual(hreflangs(src), dict(home_sync.cluster()))
        for lang in LANGS:
            self.assertIn('href="/%s/"' % lang, src)
        self.assertIn("URLSearchParams", src)
        self.assertIn("location.replace('/' + q + '/'", src)
        self.assertNotIn("navigator.languages[0]", src)
        # crawlers get no automatic redirect: the browser-language case only offers a link
        self.assertNotIn("location.replace('/' + c", src)
        for lang in LANGS:  # language pages forward an old ?lang=xx too
            self.assertIn("URLSearchParams", page(lang))

    def test_sitemap_has_home_pages(self):
        root = ET.parse(ROOT / "sitemap.xml").getroot()
        urls = {u.find(SM + "loc").text: u for u in root.findall(SM + "url")}
        for lang in [None] + LANGS:
            u = urls[home_sync.home_url(lang)]
            self.assertTrue(u.find(SM + "lastmod").text)
            self.assertEqual(len(u.findall(X)), 13)
            self.assertIsNotNone(u.find("{http://www.google.com/schemas/sitemap-image/1.1}image"))
            self.assertEqual({a.get("hreflang"): a.get("href") for a in u.findall(X)}, dict(home_sync.cluster()))
        self.assertFalse([l for l in urls if "?" in l])
        self.assertEqual(len(urls), len(root.findall(SM + "url")))  # no duplicate loc

    def test_llms_links_every_language(self):
        llms = (ROOT / "llms.txt").read_text(encoding="utf-8")
        for lang in [None] + LANGS:
            self.assertIn(home_sync.home_url(lang), llms)

    def test_service_worker(self):
        sw = (ROOT / "sw.js").read_text(encoding="utf-8")
        self.assertIn("'/en/'", sw)
        self.assertIn("'/', '/index.html'", sw)
        for ref in re.findall(r"'(/[^']*\?v=\d+)'", sw):
            if ref.startswith("/journal/"):
                continue
            self.assertIn(ref.split("?")[0], page("en") + page(None))

class HomeJournalCards(unittest.TestCase):
    """The main page of every language carries a static card section with the newest journal posts of that language."""

    def cards(self, text):
        sec = re.search(r'<section class="sec wrap" id="journal".*?</section>', text, re.S)
        self.assertIsNotNone(sec)
        return sec.group(0), re.findall(r'<a class="jcard" href="([^"]+)">', sec.group(0))

    def test_every_language_shows_three_newest_posts_in_its_language(self):
        posts = home_sync.journal_posts()
        newest = [p["slug"] for p, _d in posts][:3]
        for lang in LANGS:
            sec, hrefs = self.cards((ROOT / lang / "index.html").read_text(encoding="utf-8"))
            self.assertEqual(hrefs, ["/journal/%s/%s/" % (lang, s) for s in newest], lang)
            self.assertIn('href="/journal/%s/"' % lang, sec)  # "view all"
            self.assertEqual(sec.count("data-ipe-time"), 3)
            for p, d in posts[:3]:
                self.assertIn(d[lang]["title"].split("&")[0], sec)

    def test_localtime_script_inlined_byte_for_byte(self):
        src = (ROOT / "shared" / "ipe-localtime.js").read_bytes().decode("utf-8")
        for lang in LANGS:
            self.assertIn("<script>" + src + "</script>", (ROOT / lang / "index.html").read_text(encoding="utf-8"))

    def test_chooser_has_no_cards_or_markers(self):
        text = (ROOT / "index.html").read_text(encoding="utf-8")
        self.assertNotIn("jcard", text)
        self.assertNotIn("<!-- home:", text)

    def test_new_post_updates_the_cards(self):
        import shutil
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for name in ("scripts", "journal", "shared", "sitemap.xml", "llms.txt", "og-image.png", "icon-512.png"):
                src = ROOT / name
                (shutil.copytree if src.is_dir() else shutil.copy)(src, root / name)
            old = sorted((root / "scripts" / "journal_src").glob("*.html"))[0]
            new = root / "scripts" / "journal_src" / "2026-10-28-fourth-post.html"
            new.write_text(old.read_text(encoding="utf-8").replace(old.stem, new.stem).replace("2026-10-20", "2026-10-28"), encoding="utf-8")
            writes, errors = home_sync.build(root)
            self.assertEqual(errors, [])
            for lang in ("en", "ko"):  # no translation JSON yet -> en/ko only; other languages keep their own newest three
                _sec, hrefs = self.cards(writes[root / lang / "index.html"])
                self.assertEqual(hrefs[0], "/journal/%s/2026-10-28-fourth-post/" % lang)
                self.assertEqual(len(hrefs), 3)
            _sec, hrefs = self.cards(writes[root / "ja" / "index.html"])
            self.assertNotIn("fourth-post", "".join(hrefs))



if __name__ == "__main__":
    unittest.main()