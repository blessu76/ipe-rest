import json
import re
import sys
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
import journal_i18n  # noqa: E402
import pages_sync  # noqa: E402

LANGS = pages_sync.LANGS
PAGES = tuple(x for x in pages_sync.PAGES if x != "terms")  # terms exists only in en/ko: see EnglishOnlyPages
PL = pages_sync.page_langs  # languages that really have /<lang>/<page>/ (privacy = ko/en originals + translated, not the new 4)
NEW4 = ["zh-Hant", "th", "vi", "tr"]  # live languages without any privacy page (Davy 2026-11-12: legal text stays ko/en original)
OLD_PRIVACY = ["ja", "es", "pt-BR", "fr", "de", "id", "ar", "hi", "ru", "zh"]  # retired pre-v1.0 translations: 1-hop stubs to the English text
SM = "{http://www.sitemaps.org/schemas/sitemap/0.9}"
X = "{http://www.w3.org/1999/xhtml}link"
LD = re.compile(r'<script type="application/ld\+json">\s*(.*?)\s*</script>', re.S)


V1_EFFECTIVE = "2026-07-26"  # v1.0 effective date (owner decision); version string is "v1.0"
LEGAL = pages_sync.LEGAL_PATH  # (page, lang) -> fixed /legal/ address (current live text, scripts/legal_src); the old paths are 1-hop stubs


def served(p, lang=None):
    """File that serves the page: /<lang>/legal/<page>/ for privacy en·ko and terms en·ko, else /<lang>/<page>/."""
    if (p, lang) in LEGAL:
        return ROOT / LEGAL[(p, lang)].strip("/") / "index.html"
    return (ROOT / lang / p / "index.html") if lang else (ROOT / p / "index.html")


def read(p, lang=None):
    return served(p, lang).read_text(encoding="utf-8")


def read_old(path):
    return (ROOT / path / "index.html").read_text(encoding="utf-8")


class InfoPages(unittest.TestCase):
    def test_in_sync_and_valid(self):
        writes, errors = pages_sync.build()
        self.assertEqual(errors, [])
        stale = [str(p) for p, t in writes.items() if not p.exists() or p.read_text(encoding="utf-8") != t]
        self.assertEqual(stale, [], "run: python3 scripts/pages_sync.py")

    def test_all_12_languages_exist_for_every_page(self):
        self.assertEqual(len(LANGS), 12)
        for p in PAGES:
            for lang in PL(p):
                self.assertTrue(served(p, lang).is_file(), (p, lang))
        for p in ("about", "contact"):  # not legal text: every live language has it
            self.assertEqual(PL(p), LANGS)

    def test_privacy_exists_only_in_ko_and_en(self):
        """Legal text stays the ko/en original: other languages have no privacy page, no hreflang or sitemap entry; their links go to /en/legal/privacy/."""
        self.assertEqual(PL("privacy"), ["en", "ko"])
        sm = (ROOT / "sitemap.xml").read_text(encoding="utf-8")
        for lang in LANGS:
            if lang in ("en", "ko"):
                continue
            self.assertNotIn("https://ipe.rest/%s/privacy/" % lang, sm)
            for f in (ROOT / lang / "index.html", ROOT / "journal" / lang / "index.html",
                      ROOT / lang / "about" / "index.html", ROOT / lang / "contact" / "index.html"):
                src = f.read_text(encoding="utf-8")
                self.assertIn('href="/en/legal/privacy/"', src, f)
                self.assertNotIn('href="/%s/privacy/"' % lang, src, f)
        for lang in PL("privacy"):
            src = read("privacy", lang)
            for n in NEW4 + OLD_PRIVACY:
                self.assertNotIn('hreflang="%s"' % n, src, (lang, n))

    def test_retired_privacy_translations_are_stubs(self):
        for lang in OLD_PRIVACY:
            f = ROOT / lang / "privacy" / "index.html"
            stub = f.read_text(encoding="utf-8")
            self.assertIn('<link rel="canonical" href="https://ipe.rest/en/legal/privacy/">', stub, lang)
            self.assertIn("location.replace(\"/en/legal/privacy/\")", stub, lang)
            self.assertNotIn("<main", stub, lang)

    def test_page_head_and_body(self):
        for p in PAGES:
            want = dict(pages_sync.cluster(pages_sync.load()[0], p))
            self.assertEqual(len(want), len(PL(p)) + 1)
            for lang in PL(p):
                src = read(p, lang)
                self.assertIn('<html lang="%s" dir="%s">' % (lang, "rtl" if lang == "ar" else "ltr"), src)
                self.assertIn('<link rel="canonical" href="%s">' % pages_sync.page_url(p, lang), src)
                got = dict(re.findall(r'<link rel="alternate" hreflang="([^"]+)" href="([^"]+)">', src))
                self.assertEqual(got, want, (p, lang))
                self.assertEqual('class="ai-note"' in src, lang in pages_sync.TR, (p, lang))
                self.assertIn('<select class="ipe-lang__select"', src)
                self.assertNotIn("data-lang-select", src)
                sel = re.findall(r'<option value="([^"]*)"[^>]* selected>', src)
                self.assertEqual(sel, [LEGAL.get((p, lang), "/%s/%s/" % (lang, p))])
                self.assertEqual(len(re.findall(r'<option value="/', src)), len(PL(p)))
                ld = json.loads(LD.findall(src)[0])
                self.assertEqual(ld["@graph"][0]["inLanguage"], lang)
                self.assertEqual(ld["@graph"][0]["url"], pages_sync.page_url(p, lang))
                self.assertNotIn('data-lang="', src)
                for other in PAGES:  # internal links stay inside the page's language
                    self.assertNotIn('href="/%s/"' % other, src.split("<body>")[1])
                if p != "privacy":
                    self.assertIn("mailto:ipe.haven@gmail.com", src)
                elif (p, lang) not in LEGAL:  # the v1.0 legal text describes browser storage in words, not the key name
                    self.assertIn("ipe_lang", src)

    def test_chooser(self):
        for p in PAGES:
            src = read(p)
            self.assertIn('<link rel="canonical" href="%s">' % pages_sync.page_url(p, "en"), src)
            if p == "privacy":  # the shell is a 1-hop stub to /en/legal/privacy/, not a chooser
                self.assertIn('url=/en/legal/privacy/', src)
                continue
            for lang in PL(p):
                self.assertIn('href="/%s/%s/"' % (lang, p), src)

    def test_sitemap(self):
        root = ET.parse(ROOT / "sitemap.xml").getroot()
        urls = {u.find(SM + "loc").text: u for u in root.findall(SM + "url")}
        for p in PAGES:
            self.assertNotIn(pages_sync.page_url(p), urls)  # the language-less shell is not listed
            for lang in PL(p):
                u = urls[pages_sync.page_url(p, lang)]
                self.assertTrue(u.find(SM + "lastmod").text)
                self.assertEqual(len(u.findall(X)), len(PL(p)) + 1)
                self.assertIsNotNone(u.find("{http://www.google.com/schemas/sitemap-image/1.1}image"))
        self.assertEqual(len(urls), len(root.findall(SM + "url")))
        self.assertNotIn("https://ipe.rest/about/</loc>\n    <lastmod>2026-10-20", (ROOT / "sitemap.xml").read_text(encoding="utf-8"))

    def test_llms_and_other_pages_link_to_language_pages(self):
        llms = (ROOT / "llms.txt").read_text(encoding="utf-8")
        for p in PAGES:
            for lang in PL(p):
                self.assertIn(pages_sync.page_url(p, lang), llms)
            self.assertNotIn("(language chooser): " + pages_sync.page_url(p), llms)
        for lang in LANGS:  # main page, journal footer
            for f in (ROOT / lang / "index.html", ROOT / "journal" / lang / "index.html"):
                src = f.read_text(encoding="utf-8")
                for p in PAGES:
                    link = journal_i18n.privacy_href(lang) if p == "privacy" else "/%s/%s/" % (lang, p)
                    self.assertIn('href="%s"' % link, src, f)
                    self.assertNotIn('href="/%s/"' % p, src, f)


class EnglishOnlyPages(unittest.TestCase):
    """Terms of use: /en/legal/terms/ and /ko/legal/terms/ are the pages; /legal/terms/ is a chooser; every old address is a 1-hop stub; nothing else is generated or listed."""

    def test_terms_page_and_redirect(self):
        en, ko = "https://ipe.rest/en/legal/terms/", "https://ipe.rest/ko/legal/terms/"
        for lang, url in (("en", en), ("ko", ko)):
            src = read("terms", lang)
            self.assertIn('<link rel="canonical" href="%s">' % url, src)
            self.assertIn("privacy@ipe.rest", src)
            self.assertEqual(dict(re.findall(r'<link rel="alternate" hreflang="([^"]+)" href="([^"]+)">', src)),
                             {"x-default": en, "en": en, "ko": ko}, lang)
        # ko terms shows its own text directly (not a redirect stub)
        ko_src = read("terms", "ko")
        self.assertNotIn("http-equiv=\"refresh\"", ko_src)
        self.assertIn("<h2>1. 약관의 적용과 운영자</h2>", ko_src)
        self.assertIn("<h2>12. 문의</h2>", ko_src)
        for old, target in (("terms", "/en/legal/terms/"), ("en/terms", "/en/legal/terms/"), ("ko/terms", "/ko/legal/terms/")):  # ONE hop to the body
            stub = read_old(old)
            self.assertIn('<link rel="canonical" href="https://ipe.rest%s">' % target, stub, old)
            self.assertIn('<meta http-equiv="refresh" content="0; url=%s">' % target, stub, old)
            self.assertIn('location.replace("%s")' % target, stub, old)
            self.assertNotIn("<main", stub, old)
            self.assertNotRegex(stub, r"noindex")
        for lang in LANGS:
            if lang not in ("en", "ko"):  # other languages: noindex 1-hop stubs to the English text, old and /legal/ addresses
                for sub in ("terms", "legal/terms"):
                    stub = (ROOT / lang / sub / "index.html").read_text(encoding="utf-8")
                    self.assertIn('<meta http-equiv="refresh" content="0; url=/en/legal/terms/">', stub, (lang, sub))
                    self.assertIn('<link rel="canonical" href="https://ipe.rest/en/legal/terms/">', stub, (lang, sub))
                    self.assertIn('<meta name="robots" content="noindex,follow">', stub, (lang, sub))
                    self.assertNotIn("<main", stub, (lang, sub))
        sm = (ROOT / "sitemap.xml").read_text(encoding="utf-8")
        for url in (en, ko):
            self.assertIn("<loc>%s</loc>" % url, sm)
        for gone in ("terms/", "en/terms/", "ko/terms/"):  # stubs are not listed
            self.assertNotIn("<loc>https://ipe.rest/%s</loc>" % gone, sm)

    def test_privacy_old_addresses_are_one_hop_stubs(self):
        for old, target in (("privacy", "/en/legal/privacy/"), ("en/privacy", "/en/legal/privacy/"), ("ko/privacy", "/ko/legal/privacy/")):
            stub = read_old(old)
            self.assertIn('<link rel="canonical" href="https://ipe.rest%s">' % target, stub, old)
            self.assertIn('content="0; url=%s"' % target, stub, old)
            self.assertIn('location.replace("%s")' % target, stub, old)
            self.assertNotIn("<main", stub, old)

    def test_legal_chooser_and_six_addresses(self):
        for p in ("privacy", "terms"):
            chooser = (ROOT / "legal" / p / "index.html").read_text(encoding="utf-8")
            self.assertIn('href="/ko/legal/%s/"' % p, chooser, p)
            self.assertIn('href="/en/legal/%s/"' % p, chooser, p)
            self.assertIn(V1_EFFECTIVE, chooser, p)
            for lang in ("en", "ko"):
                out = read(p, lang)
                self.assertIn('<html lang="%s"' % lang, out, (p, lang))
                self.assertIn(V1_EFFECTIVE, out, (p, lang))
                self.assertNotRegex(out, r"2FA|2단계", (p, lang))
                self.assertIn('href="%s"' % pages_sync.LEGAL_PATH[(p, "ko" if lang == "en" else "en")], out, (p, lang))

    def test_legal_bodies_are_the_v1_text(self):
        """The /legal/ pages are scripts/legal_src/* (v1.0 text converted from the _ipe md) with only the address paths rewritten — never a template."""
        for (p, lang), name in pages_sync.LEGAL_SRC.items():
            src = (ROOT / "scripts" / "legal_src" / name).read_text(encoding="utf-8")
            out = read(p, lang)
            for a, b in pages_sync.LEGAL_REWRITE:
                src = src.replace(a, b)
            out = re.sub(r'<p class="legal-switch".*?</p>\n', "", out, count=1, flags=re.S)
            # header select (kit langswitch), its style and script are the only generated additions
            out = re.sub(r'<div class="ipe-lang">.*?</div>', "<LANG/>", out, count=1, flags=re.S)
            src = re.sub(r'<label class="language">.*?</label>', "<LANG/>", src, count=1, flags=re.S)
            out = re.sub(r'<style>\n\.ipe-lang\{.*?</style>\n(?=</head>)', "", out, count=1, flags=re.S)
            out = re.sub(r'<script src="/shared/ipe-lang\.js[^>]*></script>\n', "", out, count=1)
            # ipe_theme additions (pre-paint script, dark CSS, header toggle)
            out = re.sub(r'\n<script>\(function\(\)\{var d=document\.documentElement,k=\'ipe_theme\'.*?</script>', "", out, count=1, flags=re.S)
            out = re.sub(r'<style>\n\.ipe-theme\{.*?</style>\n(?=</head>)', "", out, count=1, flags=re.S)
            out = re.sub(r'<button class="ipe-theme".*?</button>', "", out, count=1, flags=re.S)
            src = re.sub(r'journal\.js\?v=\w+', "journal.js", src)
            out = re.sub(r'journal\.js\?v=\w+', "journal.js", out)
            self.assertEqual(out, src, (p, lang))
            self.assertNotRegex(out, r"\{시행일\}")
            for bad in ("후보", "candidate", "확인 필요", "[confirm", "Status: v1.0", "상태: v1.0"):
                self.assertNotIn(bad, out, (p, lang, bad))
            self.assertIn("privacy@ipe.rest", out)
            self.assertIn("pawstcard", out)  # explicitly excluded from the common text
            self.assertIn("<time datetime=\"%s\">%s</time>" % (V1_EFFECTIVE, V1_EFFECTIVE), out, (p, lang))
            self.assertRegex(out, r"(?:Version|버전) v1\.0</span>")
            self.assertNotIn("ipe.haven@gmail.com", out, (p, lang))  # old live contact is gone
        ko = read("privacy", "ko")
        self.assertIn("<h2>부록 B — 앱별 차이", ko)
        self.assertNotIn("2단계 인증", ko)  # the unconfirmed 2FA claim is not published
        self.assertNotIn("two-step", read("privacy", "en"))
        self.assertIn("<h2>10. 안전성 확보 조치</h2>", ko)

    def test_every_privacy_language_links_to_its_legal_terms(self):
        for lang in PL("privacy"):
            want = 'href="%s"' % journal_i18n.legal_href("terms", lang)
            self.assertIn(want, read("privacy", lang), lang)
            self.assertNotIn('href="/en/terms/"', read("privacy", lang), lang)

    def test_privacy_describes_ads_cookies_and_subdomains(self):
        src = read("privacy", "en")
        for needle in ("AdSense", "ipe.rest", "idle.ipe.rest", "play.ipe.rest", "still.ipe.rest", "patchland.ipe.rest", "privacy@ipe.rest"):  # v1.0: pawstcard is excluded from the common policy
            self.assertIn(needle, src, needle)
        self.assertNotRegex(src, r"(?i)(this site|ipe\.rest) (shows?|has) no (ads|advertising)")
        self.assertNotRegex(src, r"(?i)idle only")


class InfoPageShellSeo(unittest.TestCase):
    """The language-less shells /about/ /contact/ /privacy/ must never compete with the /en/ pages (same incident as the journal shells).
    Rule: shell canonical + og:url = /en/<page>/, hreflang x-default = /en/<page>/ on all 13 pages, shell not in the sitemap, NO noindex."""

    SITE = "https://ipe.rest"

    def test_shell_canonical_og_and_no_noindex(self):
        for p in PAGES:
            src = read(p)
            en = pages_sync.page_url(p, "en")
            self.assertIn('<link rel="canonical" href="%s">' % en, src, p)
            if p != "privacy":  # the privacy shell is a stub (no og tags)
                self.assertIn('<meta property="og:url" content="%s">' % en, src, p)
            self.assertNotRegex(src, r'<meta name="robots" content="[^"]*noindex', p)
            self.assertNotIn('href="%s/%s/"' % (self.SITE, p), src, p)  # nothing points at the shell itself

    def test_x_default_is_en_on_every_page(self):
        for p in PAGES:
            for lang in ([None] if p != "privacy" else []) + PL(p):
                src = read(p, lang)
                m = re.search(r'<link rel="alternate" hreflang="x-default" href="([^"]+)"', src)
                self.assertEqual(m.group(1), pages_sync.page_url(p, "en"), (p, lang))

    def test_sitemap_has_no_shell_and_x_default_is_en(self):
        root = ET.parse(ROOT / "sitemap.xml").getroot()
        locs = {u.find(SM + "loc").text for u in root.findall(SM + "url")}
        for p in PAGES:
            self.assertNotIn("%s/%s/" % (self.SITE, p), locs, p)
            self.assertIn(pages_sync.page_url(p, "en"), locs, p)
        for gone in ("privacy/", "en/privacy/", "ko/privacy/", "terms/", "en/terms/", "ko/terms/"):  # stubs are not listed
            self.assertNotIn("%s/%s" % (self.SITE, gone), locs, gone)
        for want in ("en/legal/privacy/", "en/legal/terms/", "ko/legal/privacy/", "ko/legal/terms/"):
            self.assertIn("%s/%s" % (self.SITE, want), locs, want)
        for u in root.findall(SM + "url"):
            if re.search(r"/(about|contact|privacy)/$", u.find(SM + "loc").text):
                xd = [l.get("href") for l in u.findall(X) if l.get("hreflang") == "x-default"]
                self.assertEqual(len(xd), 1)
                self.assertTrue(xd[0].startswith(self.SITE + "/en/") or xd[0] == pages_sync.page_url("privacy", "en"), xd)

    def test_generator_emits_the_rule(self):
        data = pages_sync.load()[0]
        for p in PAGES:
            self.assertEqual(dict(pages_sync.cluster(data, p))["x-default"], pages_sync.page_url(p, "en"))


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
    ROOTS = ["index.html", "about/index.html", "contact/index.html", "journal/index.html"]  # /privacy/ is a stub now

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
            (p + "/index.html", "en/" + p + "/index.html") for p in ("about", "contact")
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
            n = len(LANGS)
            if re.match(r"journal/2\d{3}-", f):  # post shells: only the really translated languages (the 4 no-translation ones fall back to /en/)
                slug = f.split("/")[1]
                n = len(LANGS) - len([l for l in journal_i18n.NO_POST_TRANSLATION
                                      if not (ROOT / "scripts" / "journal_i18n" / slug / ("%s.json" % journal_i18n.K.legacy_code(l))).exists()])
            self.assertTrue(d.endswith("Available in %d languages." % n), f)
            self.assertNotIn("Choose your language", d, f)
            self.assertNotIn("…", d, f)  # no truncated description (#181)
            for prop in ("og:title", "twitter:title"):  # share previews: plain title, no marker
                self.assertNotIn("all languages", self.meta(f, prop), (f, prop))
            self.assertNotIn(" Available in", self.meta(f, "og:description"), f)

    def test_language_pages_unchanged(self):
        """Regression: none of the 12 language pages (home, info pages, journal list/posts) carries the x-default marker."""
        n = 0
        for f in sorted(ROOT.glob("*/index.html")) + sorted(ROOT.glob("*/*/index.html")) + sorted(ROOT.glob("journal/*/*/index.html")):
            rel = f.relative_to(ROOT).as_posix()
            if rel.split("/")[0] in ("scripts", "tests", "fonts", ".git", "legal") or rel in self.roots():
                continue
            h = f.read_text(encoding="utf-8")
            t = re.search(r"<title>(.*?)</title>", h)
            if not t:
                continue
            n += 1
            self.assertNotIn(self.MARK, t.group(1), rel)
            self.assertNotIn("choose your language", t.group(1), rel)
            self.assertNotIn("Available in %d languages." % len(LANGS), h, rel)
        self.assertGreater(n, 100)

    def test_root_cards_match_x_default_posts_exactly(self):
        root = (ROOT / "journal" / "index.html").read_text(encoding="utf-8")
        cards = re.findall(r'class="post-card" href="(/journal/[^"]+)"', root)
        self.assertEqual(sorted(cards), sorted("/journal/%s/" % s for s in self.x_default_posts()))
        self.assertEqual(len(cards), len(set(cards)))

    def test_sitemap_lastmod_for_changed_roots(self):
        sm = (ROOT / "sitemap.xml").read_text(encoding="utf-8")
        for f in self.roots():
            if f.startswith("journal/") or f.split("/")[0] in PAGES:
                continue  # journal + info-page shells canonicalise to /en/... and are deliberately not in the sitemap (JournalShellSeo, InfoPageShellSeo)
            loc = "https://ipe.rest/" + f.replace("index.html", "")
            m = re.search(r"<loc>%s</loc>\s*<lastmod>([^<]+)</lastmod>" % re.escape(loc), sm)
            self.assertIsNotNone(m, loc)
            self.assertGreaterEqual(m.group(1), "2026-10-26", loc)


if __name__ == "__main__":
    unittest.main()


class DistinctTitles(unittest.TestCase):
    """The same page in two languages must not share one <title> (duplicate-title SEO finding, fr = en)."""

    def test_list_and_contact_titles_differ_between_languages(self):
        import re
        root = Path(__file__).resolve().parent.parent
        for rel in ("journal/{l}/index.html", "{l}/contact/index.html"):
            seen = {}
            for l in LANGS:
                src = (root / rel.format(l=l)).read_text(encoding="utf-8")
                t = re.search(r"<title>(.*?)</title>", src).group(1).strip().lower()
                self.assertNotIn(t, seen, "%s duplicates %s title %r" % (l, seen.get(t), t))
                seen[t] = l


class GoAndOgImage(unittest.TestCase):
    """/go/<track>/ redirect pages are never indexed; the shared OG image is 1200x630 and every page declares that size."""

    ROOT = Path(__file__).resolve().parent.parent

    def test_every_go_page_is_noindex_and_robots_does_not_block_it(self):
        pages = sorted((self.ROOT / "go").glob("*/index.html"))
        self.assertTrue(pages)
        for f in pages:
            self.assertRegex(f.read_text(encoding="utf-8"), r'<meta name="robots" content="noindex', str(f))
        # noindex only works if crawlers may fetch the page
        self.assertNotRegex((self.ROOT / "robots.txt").read_text(encoding="utf-8"), r"(?m)^Disallow:\s*/go")
        sm = (self.ROOT / "sitemap.xml").read_text(encoding="utf-8")
        self.assertNotIn("/go/", sm)

    def test_og_image_is_1200x630_and_declared_sizes_match(self):
        import struct
        w, h = struct.unpack(">II", (self.ROOT / "og-image.png").read_bytes()[16:24])
        self.assertEqual((w, h), (1200, 630))
        for f in self.ROOT.rglob("index.html"):
            if f.relative_to(self.ROOT).parts[0] in ("scripts", "tests", ".git"):
                continue
            src = f.read_text(encoding="utf-8")
            if "https://ipe.rest/og-image.png" in src:
                for k, v in (("width", 1200), ("height", 630)):
                    m = re.search(r'og:image:%s" content="(\d+)"' % k, src)
                    if m:
                        self.assertEqual(int(m.group(1)), v, str(f))


class FooterLinks(unittest.TestCase):
    """Every language's home, info and journal-index footer links about, contact, privacy and the English-only terms page."""

    def test_footers_link_the_four_legal_info_pages(self):
        for lang in LANGS:
            pages = [("home", ROOT / lang / "index.html"), ("about", ROOT / lang / "about" / "index.html"),
                     ("journal", ROOT / "journal" / lang / "index.html")]
            if lang in PL("privacy"):
                pages.append(("privacy", served("privacy", lang)))
            for name, f in pages:
                src = f.read_text(encoding="utf-8")
                foot = src[src.rindex("<footer"):]
                terms = journal_i18n.legal_href("terms", lang)
                for href in ("/%s/about/" % lang, "/%s/contact/" % lang, journal_i18n.privacy_href(lang), terms):
                    if name == "privacy" and ("privacy", lang) in LEGAL:  # the /legal/ copies carry the rewritten addresses
                        for a, b in pages_sync.LEGAL_REWRITE:
                            href = href.replace(a, b)
                    self.assertIn('href="%s"' % href, foot, "%s footer (%s) lacks %s" % (name, lang, href))


class HeaderJournalNav(unittest.TestCase):
    """Every live language's header nav links its own journal index, on the home, info and journal pages."""

    def test_header_nav_links_same_language_journal(self):
        for lang in LANGS:
            files = [ROOT / lang / "index.html", ROOT / lang / "about" / "index.html",
                     ROOT / lang / "contact" / "index.html", ROOT / "journal" / lang / "index.html"]
            files += sorted((ROOT / "journal" / lang).glob("*/index.html"))
            for f in files:
                m = re.search(r'<nav[^>]*aria-label="Primary"[^>]*>(.*?)</nav>', f.read_text(encoding="utf-8"), re.S)
                self.assertIsNotNone(m, "no primary nav in %s" % f)
                self.assertIn('href="/journal/%s/"' % lang, m.group(1), "header journal link missing: %s" % f)


class SharedLangAsset(unittest.TestCase):
    def test_ipe_lang_js_is_the_vendored_kit_file(self):
        kit = (ROOT / "vendor" / "ipe_web_kit" / "assets" / "ipe-lang.js").read_bytes()
        self.assertEqual((ROOT / "shared" / "ipe-lang.js").read_bytes(), kit)
