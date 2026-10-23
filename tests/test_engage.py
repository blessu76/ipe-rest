import re
import shutil
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
import journal_i18n as I18N  # noqa: E402
import journal_sync  # noqa: E402

JS = (ROOT / "widget" / "ipe-engage.js").read_text(encoding="utf-8")
CSS = (ROOT / "widget" / "ipe-engage.css").read_text(encoding="utf-8")
RULES = (ROOT / "firebase" / "firestore.rules").read_text(encoding="utf-8")
SW = (ROOT / "sw.js").read_text(encoding="utf-8")
SRC = ROOT / "scripts" / "journal_src"
STRINGS = ("like", "liked", "comments", "empty", "name", "text", "send", "sending", "sent", "wait", "nolinks", "invalid",
           "error", "more", "unavailable", "hint")


def slugs():
    return sorted(f.stem for f in SRC.glob("*.html") if journal_sync.DIR_RE.match(f.stem))


def widget_strings():
    block = JS[JS.index("var T = {"):JS.index("function el(")]
    out = {}
    for m in re.finditer(r"^\s{4}(\w\w): \{(.*)\},?$", block, re.M):
        out[m.group(1)] = re.findall(r"(\w+): '", m.group(2))
    return out


class EngageWidget(unittest.TestCase):
    def test_every_post_page_mounts_the_widget(self):
        for slug in slugs():
            for lang in I18N.LANGS:
                src = (ROOT / "journal" / lang / slug / "index.html").read_text(encoding="utf-8")
                mount = '<section class="ipe-engage" data-site="ipe.rest" data-post="%s" data-lang="%s"></section>' % (slug, lang)
                self.assertEqual(src.count(mount), 1, (slug, lang))
                self.assertLess(src.index(mount), src.index('class="back"'))
                self.assertIn('/widget/ipe-engage.css?v=%s' % I18N.ENGAGE_VER, src)
                self.assertLess(src.index("/widget/ipe-engage.js?v=%s" % I18N.ENGAGE_VER), src.index("/journal/journal.js"))

    def test_lists_and_choosers_do_not_load_the_widget(self):
        for lang in I18N.LANGS:
            self.assertNotIn("ipe-engage", (ROOT / "journal" / lang / "index.html").read_text(encoding="utf-8"))
        self.assertNotIn("ipe-engage", (ROOT / "journal" / "index.html").read_text(encoding="utf-8"))
        for slug in slugs():
            self.assertNotIn("ipe-engage", (ROOT / "journal" / slug / "index.html").read_text(encoding="utf-8"))

    def test_widget_text_in_all_12_languages_with_same_keys(self):
        got = widget_strings()
        self.assertEqual(sorted(got), sorted(I18N.LANGS))
        for lang, keys in got.items():
            self.assertEqual(sorted(keys), sorted(STRINGS), lang)

    def test_widget_safety(self):
        self.assertNotIn("innerHTML", JS)  # comments are rendered as text only
        self.assertIn("firestore.googleapis.com", JS)
        self.assertIn("localStorage", JS)
        self.assertIn("ie-trap", JS)  # honeypot
        self.assertIn("GAP_MS = 30000", JS)
        self.assertIn("REQUEST_TIME", JS)
        self.assertIn("IntersectionObserver", JS)
        self.assertRegex(CSS, r"prefers-color-scheme:dark")
        self.assertIn('[data-theme="dark"]', CSS)

    @unittest.skipUnless(shutil.which("node"), "node 없음")
    def test_widget_js_parses(self):
        r = subprocess.run(["node", "--check", str(ROOT / "widget" / "ipe-engage.js")], capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stderr)

    def test_service_worker_never_caches_firestore(self):
        self.assertIn("firestore.googleapis.com", SW)
        i = SW.index("firestore.googleapis.com")
        self.assertLess(i, SW.index("const isHTML"))
        m = re.search(r"const CACHE = 'ipe-v(\d+)'", SW)
        self.assertGreaterEqual(int(m.group(1)), 36)

    def test_rules_defence_line(self):
        for needle in ("allow update, delete: if false;", "request.resource.data.createdAt == request.time",
                       "request.resource.data.count == resource.data.count + 1", "request.resource.data.count == 1",
                       "allow read, write: if false;", "cleanText(request.resource.data.name, 30)",
                       "cleanText(request.resource.data.text, 500)", "hasOnly(['name', 'text', 'createdAt'])",
                       "ipe\\\\.rest"):
            self.assertIn(needle, RULES)
        self.assertNotIn("allow list", RULES.split("match /comments/")[0])  # posts cannot be enumerated
        # the client link filter and the rule use the same pattern
        self.assertIn("https?:|www\\\\.|://", RULES)
        self.assertIn("(https?:|www\\.|:\\/\\/)", JS)

    def test_privacy_mentions_firebase_in_all_languages(self):
        for lang in I18N.LANGS:
            src = (ROOT / lang / "privacy" / "index.html").read_text(encoding="utf-8")
            self.assertIn("Google Firebase", src, lang)

    def test_firebase_dir_not_shipped(self):
        self.assertIn("--exclude='/firebase/'", (ROOT / "scripts" / "build_site.sh").read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
