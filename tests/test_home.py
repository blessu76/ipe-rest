import json
import re
import sys
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
import home_sync  # noqa: E402
import journal_i18n as J  # noqa: E402

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
            self.assertEqual(src.count('property="og:locale:alternate"'), len(LANGS) - 1)
            self.assertEqual(hreflangs(src), want)  # all 12 + x-default, identical on every page (mutual)
            self.assertIn("G-XG4BH800J0", src)  # GA tag on every language page
            self.assertIn("/journal/%s/" % lang, src)
            self.assertNotIn('href="/journal/en/"', src) if lang != "en" else None
            self.assertIn("ipe() · idle", src)
            body = re.sub(r"<script>.*?</script>|<!--.*?-->", "", src, flags=re.S)
            # no query-string URLs of our own
            self.assertNotIn("?lang=", body)

    def test_play_portal_not_on_the_umbrella_home(self):
        # Davy 2026-11-07: ipe.rest must not carry play.ipe.rest (card, footer link, JSON-LD, FAQ, llms.txt)
        for lang in LANGS:
            src = page(lang)
            self.assertNotIn("play.ipe.rest", src, lang)
            self.assertNotIn("work-play", src, lang)
        self.assertNotIn("play.ipe.rest", (ROOT / "index.html").read_text(encoding="utf-8"))
        llms = (ROOT / "llms.txt").read_text(encoding="utf-8")
        self.assertNotIn("play.ipe.rest", llms)
        self.assertNotIn("only product", llms)
        self.assertIn("idle.ipe.rest", llms)

    def test_titles_and_descriptions_are_per_language(self):
        titles = set()
        for lang in LANGS:
            src = page(lang)
            t = re.search(r"<title>(.*?)</title>", src).group(1)
            titles.add(t)
            self.assertIn('content="%s"' % home_sync.esc(json.loads((ROOT / "scripts/home_i18n" / (J.K.legacy_code(lang) + ".json")).read_text(encoding="utf-8"))["meta_desc"]), src)
            self.assertEqual(src.count('property="og:title" content="%s"' % home_sync.esc(t.replace("&amp;", "&"))), 1, lang)
        self.assertEqual(len(titles), len(LANGS))

    def test_non_english_home_titles_have_no_tagline_tail(self):
        tail = " · when the process finally rests"
        for lang in LANGS:
            t = re.search(r"<title>(.*?)</title>", page(lang)).group(1)
            if lang == "en":
                self.assertTrue(t.endswith(tail), t)
            else:
                self.assertNotIn("when the process", t, lang)
                self.assertTrue(t.startswith("ipe() — "), t)
        # x-default root keeps its own title
        self.assertIn("<title>ipe() — quiet things for busy minds (all languages)</title>", page(None))

    def test_og_and_twitter_titles_match_title(self):
        for lang in LANGS:
            src = page(lang)
            t = re.search(r"<title>(.*?)</title>", src).group(1)
            self.assertEqual(re.search(r'<meta property="og:title" content="([^"]*)">', src).group(1), home_sync.esc(t.replace("&amp;", "&")), lang)
            self.assertEqual(re.search(r'<meta name="twitter:title" content="([^"]*)">', src).group(1), home_sync.esc(t.replace("&amp;", "&")), lang)

    def test_home_title_length_per_language(self):
        cjk = {"ja", "zh", "ko"}
        for lang in LANGS:
            if lang == "en":
                continue
            t = re.search(r"<title>(.*?)</title>", page(lang)).group(1)
            self.assertLessEqual(len(t), 40 if lang in cjk else 60, "%s: %s" % (lang, t))

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
        for lang in LANGS:  # the chooser markup still lists every language (crawlers and no-JS visitors stay here)
            self.assertIn('href="/%s/"' % lang, src)
        self.assertIn("URLSearchParams", src)
        self.assertNotIn("navigator.languages[0]", src)
        # common ipe language order: 1 ?lang= > 2 saved choice > 3 browser language (region stripped) > 4 English
        js = src[src.index("var VALID"):]
        order = [js.index(x) for x in ("get('lang')", "localStorage.getItem('ipe_lang')", "navigator.languages", "go('en')")]
        self.assertEqual(order, sorted(order))
        self.assertIn("split(/[-_]/)[0]", js)  # ko-KR -> ko
        self.assertIn("location.replace('/' + l + '/' + h)", js)
        self.assertIn("localStorage.setItem('ipe_lang', q)", js)  # ?lang=xx is remembered
        # crawlers are not sent away from the indexed chooser; the redirect only ever targets /xx/ (no loop)
        self.assertLess(js.index("/bot|crawl|spider"), js.index("navigator.languages"))
        for lang in LANGS:  # language pages forward an old ?lang=xx too (and remember it)
            self.assertIn("URLSearchParams", page(lang))
            self.assertIn("localStorage.setItem('ipe_lang', q)", page(lang))

    def test_links_to_other_ipe_sites_carry_the_language(self):
        want = {"idle.ipe.rest": {l: "https://idle.ipe.rest/%s/" % J.K.legacy_code(l) for l in LANGS}}
        for lang in LANGS:
            src = page(lang)
            for host, urls in want.items():
                found = set(re.findall(r'<a [^>]*href="(https://%s[^"]*)"' % re.escape(host), src))
                self.assertEqual(found, {urls[lang]}, (lang, host))
            for h in ("about", "contact", "privacy"):  # info pages and journal posts link idle in their own language too
                if h == "privacy" and lang in J.NO_PRIVACY_TRANSLATION:
                    continue  # legal text is not translated: no /<lang>/privacy/ page (see test_pages.test_privacy_is_not_translated_for_new_languages)
                self.assertEqual(set(re.findall(r'<a [^>]*href="(https://idle\.ipe\.rest[^"]*)"', (ROOT / lang / h / "index.html").read_text(encoding="utf-8"))) - {want["idle.ipe.rest"][lang]}, set(), (lang, h))

    def test_x_default_shells_follow_the_same_order(self):
        js = (ROOT / "journal" / "journal.js").read_text(encoding="utf-8")
        block = js[js.index("hasAttribute('data-chooser')"):js.index("// GA4")]
        order = [block.index(x) for x in ("get('lang')", "localStorage.getItem('ipe_lang')", "navigator.languages", "want = 'en'")]
        self.assertEqual(order, sorted(order))
        self.assertLess(block.index("/bot|crawl|spider"), block.index("navigator.languages"))

    def test_sitemap_has_home_pages(self):
        root = ET.parse(ROOT / "sitemap.xml").getroot()
        urls = {u.find(SM + "loc").text: u for u in root.findall(SM + "url")}
        for lang in [None] + LANGS:
            u = urls[home_sync.home_url(lang)]
            self.assertTrue(u.find(SM + "lastmod").text)
            self.assertEqual(len(u.findall(X)), len(LANGS) + 1)
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
        return sec.group(0), re.findall(r'<a class="jcard-link" href="([^"]+)">', sec.group(0))

    def test_every_language_shows_three_newest_posts_in_its_language(self):
        posts = home_sync.journal_posts()
        newest = [p["slug"] for p, _d in posts][:3]
        for lang in LANGS:
            sec, hrefs = self.cards((ROOT / lang / "index.html").read_text(encoding="utf-8"))
            self.assertEqual(hrefs, ["/journal/%s/%s/" % (lang, s) for s in newest], lang)
            self.assertIn('href="/journal/%s/"' % lang, sec)  # "view all"
            self.assertRegex(sec, r"J-\d+")
            self.assertEqual(sec.count("data-ipe-time"), 3)
            for p, d in posts[:3]:
                self.assertIn(d[lang]["title"].split("&")[0], sec)
            if lang in J.NO_POST_TRANSLATION:  # fallback cards: EN original text marked lang="en", linking the language's own fallback page
                self.assertEqual(sec.count('<p class="jcard-ex" lang="en">'), 3, lang)
                self.assertEqual(sec.count('<h3 lang="en">'), 3, lang)
                for p, d in posts[:3]:
                    self.assertEqual(d[lang]["title"], d["en"]["title"])
            else:
                self.assertNotIn('lang="en"', sec, lang)

    def test_localtime_script_inlined_byte_for_byte(self):
        src = (ROOT / "shared" / "ipe-localtime.js").read_bytes().decode("utf-8")
        for lang in LANGS:
            self.assertIn("<script>" + src + "</script>", (ROOT / lang / "index.html").read_text(encoding="utf-8"))

    def test_chooser_has_no_cards_or_markers(self):
        text = (ROOT / "index.html").read_text(encoding="utf-8")
        self.assertNotIn("jcard-link", text)
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
            new = root / "scripts" / "journal_src" / "2027-01-01-fourth-post.html"
            new.write_text(old.read_text(encoding="utf-8").replace(old.stem, new.stem).replace("2026-10-20", "2027-01-01"), encoding="utf-8")
            writes, errors = home_sync.build(root)
            self.assertEqual(errors, [])
            for lang in ("en", "ko"):  # no translation JSON yet -> en/ko only; other languages keep their own newest three
                _sec, hrefs = self.cards(writes[root / lang / "index.html"])
                self.assertEqual(hrefs[0], "/journal/%s/2027-01-01-fourth-post/" % lang)
                self.assertEqual(len(hrefs), 3)
            _sec, hrefs = self.cards(writes[root / "ja" / "index.html"])
            self.assertNotIn("fourth-post", "".join(hrefs))



if __name__ == "__main__":
    unittest.main()