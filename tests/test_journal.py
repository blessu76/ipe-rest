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
            self.assertEqual(len(u.findall("{http://www.w3.org/1999/xhtml}link")), 3)
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
        errs = self.build_with(lambda s: re.sub(r'"dateModified": "[\d-]+"', '"dateModified": "YYYY-MM-DD"', s))
        self.assertTrue(any("YYYY-MM-DD" in e for e in errs), errs)
        errs = self.build_with(lambda s: re.sub(r'"dateModified": "[\d-]+"', '"dateModified": "2026-13-45"', s))
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

if __name__ == "__main__":
    unittest.main()
