"""Draft queue (scripts/journal_queue/<slug>/): undated drafts that must stay out of the site, sitemap and feed."""
import json
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
QUEUE = ROOT / "scripts" / "journal_queue"
FILES = ["ja", "zh-Hant", "es", "pt", "fr", "de", "id", "th", "vi", "tr"]  # + en/ko in source.html (pt.json = pt-BR)
KEYS = {"title", "h1_html", "description", "abstract", "excerpt", "body"}


def words(html):
    return len(re.sub(r"<[^>]+>", " ", html).split())


def drafts():
    return sorted(d for d in QUEUE.iterdir() if d.is_dir())


class JournalQueue(unittest.TestCase):
    def test_at_least_three_drafts(self):
        self.assertGreaterEqual(len(drafts()), 3)

    def test_each_draft_is_complete_and_undated(self):
        for d in drafts():
            src = (d / "source.html").read_text(encoding="utf-8")
            self.assertNotRegex(d.name, r"^\d{4}-\d{2}-\d{2}", d.name)
            self.assertIn('<meta name="ipe:original" content="en">', src, d.name)
            self.assertNotRegex(src, r"\bTODO\b", d.name)
            self.assertNotIn('<meta name="ipe:copy-review', src, d.name)  # empty until Iris reviews it
            self.assertIn("YYYY-MM-DDTHH:MM", src, d.name)
            self.assertNotRegex(src, r"20\d\d-\d\d-\d\d", d.name)  # no real date yet
            en = re.search(r'<div class="prose" lang="en">(.*?)\n  </div>', src, re.S).group(1)
            self.assertGreaterEqual(words(en), 400, d.name)
            self.assertIn('<div class="prose" lang="ko">', src, d.name)
            for code in FILES:
                data = json.loads((d / "i18n" / ("%s.json" % code)).read_text(encoding="utf-8"))
                self.assertEqual(set(data), KEYS, "%s/%s" % (d.name, code))
                self.assertTrue(all(isinstance(v, str) and v.strip() for v in data.values()), "%s/%s" % (d.name, code))
                self.assertGreater(len(data["body"]), 600, "%s/%s" % (d.name, code))
            self.assertEqual(len(list((d / "i18n").glob("*.json"))), len(FILES), d.name)

    def test_drafts_are_not_served_anywhere(self):
        served = "".join((ROOT / f).read_text(encoding="utf-8") for f in ("sitemap.xml", "llms.txt", "journal/feed.xml"))
        for d in drafts():
            self.assertNotIn(d.name, served, d.name)
            self.assertFalse(list((ROOT / "journal").glob("**/*%s*" % d.name)), d.name)


if __name__ == "__main__":
    unittest.main()
