"""Dark theme: localStorage key ipe_theme, pre-paint script in <head>, header toggle on every page that has the language select."""
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


class DarkTheme(unittest.TestCase):
    def test_every_page_with_the_language_select_has_the_toggle_and_a_head_script(self):
        n = 0
        for p in ROOT.rglob("*.html"):
            if ".git" in p.parts or "scripts" in p.parts or "vendor" in p.parts:
                continue
            t = p.read_text(encoding="utf-8")
            if 'class="ipe-lang"' not in t:
                continue
            n += 1
            rel = p.relative_to(ROOT)
            self.assertEqual(t.count('class="ipe-theme"'), 1, rel)
            head = t[:t.index("</head>")]
            self.assertIn("localStorage.getItem(k)", head, rel)  # FOUC guard runs in <head>, before paint
            self.assertIn("ipe_theme", head, rel)
            self.assertLess(t.index("<script>(function(){var d=document.documentElement,k='ipe_theme'"), t.index("<style"), rel)
        self.assertGreater(n, 100)

    def test_single_storage_key(self):
        t = (ROOT / "en" / "index.html").read_text(encoding="utf-8")
        self.assertIn("k='ipe_theme'", t)
        self.assertIn('data-theme="dark"', t)

    def test_toggle_label_is_localized(self):
        self.assertIn('aria-label="다크 모드 전환"', (ROOT / "ko" / "index.html").read_text(encoding="utf-8"))
        self.assertIn('aria-label="Toggle dark mode"', (ROOT / "en" / "index.html").read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
