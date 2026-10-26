import json
import re
import sys
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
import pages_sync  # noqa: E402

LANGS = pages_sync.LANGS
PAGES = pages_sync.PAGES
SM = "{http://www.sitemaps.org/schemas/sitemap/0.9}"
X = "{http://www.w3.org/1999/xhtml}link"
LD = re.compile(r'<script type="application/ld\+json">\s*(.*?)\s*</script>', re.S)


def read(p, lang=None):
    return ((ROOT / lang / p / "index.html") if lang else (ROOT / p / "index.html")).read_text(encoding="utf-8")


class InfoPages(unittest.TestCase):
    def test_in_sync_and_valid(self):
        writes, errors = pages_sync.build()
        self.assertEqual(errors, [])
        stale = [str(p) for p, t in writes.items() if not p.exists() or p.read_text(encoding="utf-8") != t]
        self.assertEqual(stale, [], "run: python3 scripts/pages_sync.py")

    def test_all_12_languages_exist_for_every_page(self):
        for p in PAGES:
            for lang in LANGS:
                self.assertTrue((ROOT / lang / p / "index.html").is_file(), (p, lang))

    def test_page_head_and_body(self):
        for p in PAGES:
            want = dict(pages_sync.cluster(pages_sync.load()[0], p))
            self.assertEqual(len(want), 13)
            for lang in LANGS:
                src = read(p, lang)
                self.assertIn('<html lang="%s" dir="%s">' % (lang, "rtl" if lang == "ar" else "ltr"), src)
                self.assertIn('<link rel="canonical" href="https://ipe.rest/%s/%s/">' % (lang, p), src)
                got = dict(re.findall(r'<link rel="alternate" hreflang="([^"]+)" href="([^"]+)">', src))
                self.assertEqual(got, want, (p, lang))
                self.assertEqual('class="ai-note"' in src, lang in pages_sync.TR, (p, lang))
                self.assertIn('<select class="lang" data-lang-select', src)
                sel = re.findall(r'<option value="([^"]*)"[^>]* selected>', src)
                self.assertEqual(sel, ["/%s/%s/" % (lang, p)])
                self.assertEqual(len(re.findall(r'<option value="/', src)), 12)
                ld = json.loads(LD.findall(src)[0])
                self.assertEqual(ld["@graph"][0]["inLanguage"], lang)
                self.assertEqual(ld["@graph"][0]["url"], "https://ipe.rest/%s/%s/" % (lang, p))
                self.assertNotIn('data-lang="', src)
                for other in PAGES:  # internal links stay inside the page's language
                    self.assertNotIn('href="/%s/"' % other, src.split("<body>")[1])
                if p != "privacy":
                    self.assertIn("mailto:ipe.haven@gmail.com", src)
                else:
                    self.assertIn("ipe_lang", src)

    def test_chooser(self):
        for p in PAGES:
            src = read(p)
            self.assertIn('<link rel="canonical" href="https://ipe.rest/%s/">' % p, src)
            for lang in LANGS:
                self.assertIn('href="/%s/%s/"' % (lang, p), src)

    def test_sitemap(self):
        root = ET.parse(ROOT / "sitemap.xml").getroot()
        urls = {u.find(SM + "loc").text: u for u in root.findall(SM + "url")}
        for p in PAGES:
            for lang in [None] + LANGS:
                u = urls[pages_sync.page_url(p, lang)]
                self.assertTrue(u.find(SM + "lastmod").text)
                self.assertEqual(len(u.findall(X)), 13)
                self.assertIsNotNone(u.find("{http://www.google.com/schemas/sitemap-image/1.1}image"))
        self.assertEqual(len(urls), len(root.findall(SM + "url")))
        self.assertNotIn("https://ipe.rest/about/</loc>\n    <lastmod>2026-10-20", (ROOT / "sitemap.xml").read_text(encoding="utf-8"))

    def test_llms_and_other_pages_link_to_language_pages(self):
        llms = (ROOT / "llms.txt").read_text(encoding="utf-8")
        for p in PAGES:
            for lang in [None] + LANGS:
                self.assertIn(pages_sync.page_url(p, lang), llms)
        for lang in LANGS:  # main page, journal footer
            for f in (ROOT / lang / "index.html", ROOT / "journal" / lang / "index.html"):
                src = f.read_text(encoding="utf-8")
                for p in PAGES:
                    self.assertIn('href="/%s/%s/"' % (lang, p), src, f)
                    self.assertNotIn('href="/%s/"' % p, src, f)


class RootLangPicker(unittest.TestCase):
    def test_focus_visible_has_outline(self):
        css = (ROOT / "index.html").read_text(encoding="utf-8")
        self.assertRegex(
            css, r"\.lg:focus-visible\{outline:2px solid var\(--cobalt\);outline-offset:2px\}"
        )
        self.assertNotIn("outline:0", css)


class XDefaultSeo(unittest.TestCase):
    """x-default (root) pages must not share title/description with their /en/ twin; language pages stay untouched."""

    MARK = "(all languages)"
    ROOTS = ["index.html", "about/index.html", "contact/index.html", "privacy/index.html", "journal/index.html"]

    def meta(self, path, prop=None):
        h = (ROOT / path).read_text(encoding="utf-8")
        if prop:
            return re.search(r'<meta (?:property|name)="%s" content="(.*?)"' % re.escape(prop), h).group(1)
        return (re.search(r"<title>(.*?)</title>", h).group(1),
                re.search(r'<meta name="description" content="(.*?)"', h).group(1))

    def x_default_posts(self):
        return sorted(p.parent.name for p in (ROOT / "journal").glob("2026-*/index.html"))

    def roots(self):
        return self.ROOTS + ["journal/%s/index.html" % s for s in self.x_default_posts()]

    def test_root_differs_from_en(self):
        pairs = [("index.html", "en/index.html")] + [
            (p + "/index.html", "en/" + p + "/index.html") for p in ("about", "contact", "privacy")
        ] + [("journal/index.html", "journal/en/index.html")] + [
            ("journal/%s/index.html" % s, "journal/en/%s/index.html" % s) for s in self.x_default_posts()]
        self.assertGreaterEqual(len(pairs), 10)
        for root, en in pairs:
            (rt, rd), (et, ed) = self.meta(root), self.meta(en)
            self.assertNotEqual(rt, et, root)
            self.assertNotEqual(rd, ed, root)
            self.assertTrue(rt.endswith(self.MARK), root)

    def test_marker_title_short_desc_one_colon(self):
        for f in self.roots():
            t, d = self.meta(f)
            self.assertLessEqual(len(t), 80, f)
            self.assertLessEqual(len(d), 160, f)
            self.assertTrue(d.endswith("Available in 12 languages."), f)
            self.assertNotIn("Choose your language", d, f)
            for prop in ("og:title", "twitter:title"):  # share previews: plain title, no marker
                self.assertNotIn("all languages", self.meta(f, prop), (f, prop))
            self.assertNotIn(" Available in", self.meta(f, "og:description"), f)

    def test_language_pages_unchanged(self):
        """Regression: none of the 12 language pages (home, info pages, journal list/posts) carries the x-default marker."""
        n = 0
        for f in sorted(ROOT.glob("*/index.html")) + sorted(ROOT.glob("*/*/index.html")) + sorted(ROOT.glob("journal/*/*/index.html")):
            rel = f.relative_to(ROOT).as_posix()
            if rel.split("/")[0] in ("scripts", "tests", "fonts", ".git") or rel in self.roots():
                continue
            h = f.read_text(encoding="utf-8")
            t = re.search(r"<title>(.*?)</title>", h)
            if not t:
                continue
            n += 1
            self.assertNotIn(self.MARK, t.group(1), rel)
            self.assertNotIn("choose your language", t.group(1), rel)
            self.assertNotIn("Available in 12 languages.", h, rel)
        self.assertGreater(n, 100)

    def test_root_cards_match_x_default_posts_exactly(self):
        root = (ROOT / "journal" / "index.html").read_text(encoding="utf-8")
        cards = re.findall(r'class="post-card" href="(/journal/[^"]+)"', root)
        self.assertEqual(sorted(cards), sorted("/journal/%s/" % s for s in self.x_default_posts()))
        self.assertEqual(len(cards), len(set(cards)))

    def test_sitemap_lastmod_for_changed_roots(self):
        sm = (ROOT / "sitemap.xml").read_text(encoding="utf-8")
        for f in self.roots():
            loc = "https://ipe.rest/" + f.replace("index.html", "")
            m = re.search(r"<loc>%s</loc>\s*<lastmod>([^<]+)</lastmod>" % re.escape(loc), sm)
            self.assertIsNotNone(m, loc)
            self.assertGreaterEqual(m.group(1), "2026-10-26", loc)


if __name__ == "__main__":
    unittest.main()
