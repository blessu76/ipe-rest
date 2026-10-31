import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SKIP = {"node_modules", ".git", "scripts", "tests", "shared"}
REQUIRED = [
    r'<meta property="og:image:width" content="1200">',
    r'<meta property="og:image:height" content="630">',
    r'<meta property="og:image:alt" content="[^"]+">',
    r'<meta name="twitter:image:alt" content="[^"]+">',
]


class OgImageMeta(unittest.TestCase):
    def test_every_og_image_page_has_size_and_alt(self):
        checked = 0
        for p in sorted(ROOT.rglob("index.html")):
            rel = p.relative_to(ROOT)
            if rel.parts[0] in SKIP:
                continue
            html = p.read_text(encoding="utf-8")
            if 'property="og:image"' not in html:
                continue
            checked += 1
            for pat in REQUIRED:
                self.assertEqual(len(re.findall(pat, html)), 1, "%s: %s" % (rel, pat))
        self.assertGreater(checked, 100)


if __name__ == "__main__":
    unittest.main()
