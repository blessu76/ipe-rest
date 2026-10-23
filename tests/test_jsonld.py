"""JSON-LD @id graph: every served page's JSON-LD is valid and every @id reference points to a node defined on this site."""
import json
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SITE = "https://ipe.rest"
LD = re.compile(r'<script type="application/ld\+json"[^>]*>\s*(.*?)\s*</script>', re.S)
SKIP = ("scripts", "tests", "_site", ".git", ".github", "node_modules")


def pages():
    for f in sorted(ROOT.rglob("*.html")):
        rel = f.relative_to(ROOT)
        if rel.parts[0] in SKIP or rel.name == "_TEMPLATE.html":
            continue
        yield rel, f.read_text(encoding="utf-8")


def page_url(rel):
    parts = rel.parts[:-1]
    return SITE + "/" + "".join(p + "/" for p in parts)


def nodes(o):
    """Every dict in a JSON-LD tree."""
    stack = [o]
    while stack:
        x = stack.pop()
        if isinstance(x, dict):
            yield x
            stack.extend(x.values())
        elif isinstance(x, list):
            stack.extend(x)


class JsonLdGraph(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.defs, cls.refs, cls.urls, cls.n = {}, {}, set(), 0
        for rel, html in pages():
            cls.urls.add(page_url(rel))
            for raw in LD.findall(html):
                cls.n += 1
                try:
                    data = json.loads(raw)
                except ValueError as e:
                    raise AssertionError("invalid JSON-LD in %s: %s" % (rel, e))
                for n in nodes(data):
                    if "@id" in n:
                        (cls.refs if set(n) == {"@id"} else cls.defs)[n["@id"]] = str(rel)

    def test_has_blocks(self):
        self.assertGreater(self.n, 100)

    def test_ids_are_site_urls(self):
        for i in list(self.defs) + list(self.refs):
            self.assertTrue(i.startswith(SITE + "/"), i)

    def test_fixed_nodes_defined(self):
        for i in (SITE + "/#organization", SITE + "/#website"):
            self.assertIn(i, self.defs, i)

    def test_every_reference_is_defined(self):
        missing = {}
        for i, where in self.refs.items():
            if i in self.defs:
                continue
            if "#" not in i and i in self.urls:  # a bare page URL = that page itself (mainEntityOfPage)
                continue
            missing[i] = where
        self.assertEqual(missing, {})

    def test_one_organization_id(self):
        org = SITE + "/#organization"
        for rel, html in pages():
            for raw in LD.findall(html):
                for n in nodes(json.loads(raw)):
                    if n.get("@type") == "Organization" and n.get("name") == "ipe()":
                        self.assertEqual(n.get("@id"), org, str(rel))

    def test_own_website_nodes_have_ids(self):
        for rel, html in pages():
            for raw in LD.findall(html):
                for n in nodes(json.loads(raw)):
                    if n.get("@type") == "WebSite" and n.get("url", "").startswith(SITE + "/"):
                        self.assertTrue(n.get("@id", "").endswith("#website"), "%s: %s" % (rel, n))


if __name__ == "__main__":
    unittest.main()
