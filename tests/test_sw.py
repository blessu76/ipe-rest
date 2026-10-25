"""sw.js: HTML 요청은 network-first + HTTP 캐시 재검증(no-cache), 정적 자산은 cache-first."""
import re
import unittest
from pathlib import Path

SW = (Path(__file__).resolve().parent.parent / "sw.js").read_text(encoding="utf-8")


def branch(name):
    m = re.search(r"if \(isHTML\) \{(.*?)\} else \{(.*?)\n  \}\n\}\);", SW, re.S)
    assert m, "fetch handler shape changed"
    return m.group(1 if name == "html" else 2)


class ServiceWorkerTest(unittest.TestCase):
    def test_html_fetch_revalidates_with_no_cache(self):
        self.assertIn("fetch(req, { cache: 'no-cache' })", branch("html"))

    def test_html_falls_back_to_cache_offline(self):
        html = branch("html")
        self.assertIn(".catch(", html)
        self.assertIn("caches.match(req)", html)
        self.assertIn("caches.match('/index.html')", html)

    def test_static_assets_stay_cache_first(self):
        static = branch("static")
        self.assertRegex(static, r"caches\.match\(req\)\.then\(\(cached\) => cached \|\| fetch\(req\)")
        self.assertNotIn("no-cache", static)

    def test_cache_version_bumped(self):
        m = re.search(r"const CACHE = 'ipe-v(\d+)'", SW)
        self.assertTrue(m and int(m.group(1)) >= 41)


if __name__ == "__main__":
    unittest.main()
