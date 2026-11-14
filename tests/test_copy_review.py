import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
import journal_check as JC  # noqa: E402


def make(tmp, slug, review=None, date=None):
    d = Path(tmp) / "src"
    d.mkdir(exist_ok=True)
    m = '<meta name="ipe:copy-review" content="%s">' % review if review else ""
    if date:
        m += '<meta name="ipe:copy-review-date" content="%s">' % date
    (d / (slug + ".html")).write_text("<html><head>%s</head></html>" % m, encoding="utf-8")
    (Path(tmp) / "i18n" / slug).mkdir(parents=True, exist_ok=True)
    return d, Path(tmp) / "i18n"


class CopyReview(unittest.TestCase):
    def test_repo_is_clean(self):
        self.assertEqual(JC.problems(), [])

    def test_legacy_posts_need_the_legacy_value(self):
        with tempfile.TemporaryDirectory() as t:
            d, i = make(t, "2026-11-14-x")
            self.assertTrue(JC.problems(d, i))
            d, i = make(t, "2026-11-14-x", JC.LEGACY)
            self.assertEqual(JC.problems(d, i), [])

    def test_new_posts_fail_without_copy_review_and_legacy_is_not_accepted(self):
        with tempfile.TemporaryDirectory() as t:
            d, i = make(t, "2026-11-15-x")
            self.assertTrue(JC.problems(d, i))
            d, i = make(t, "2026-11-15-x", JC.LEGACY)
            self.assertTrue(any("면제" in p for p in JC.problems(d, i)))
            d, i = make(t, "2026-11-15-x", "iris", "2026-11-15")  # still missing the 10 other languages
            self.assertTrue(any("언어판 없음" in p for p in JC.problems(d, i)))


if __name__ == "__main__":
    unittest.main()
