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
            for name in ("journal", "sitemap.xml", "llms.txt"):
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
            _, errors = journal_sync.build(root)
            self.assertTrue(any("hreflang=ko" in e for e in errors))


if __name__ == "__main__":
    unittest.main()
