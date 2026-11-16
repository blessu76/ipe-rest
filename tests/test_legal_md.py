"""legal_md.py stamp output (two-date stamp: first effective + current version)."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import legal_md  # noqa: E402


class StampTest(unittest.TestCase):
    def test_two_date_ko(self):
        self.assertEqual(
            legal_md.make_stamp("ko", "2026-11-11", "v1.2", "2026-07-26", "v1.0"),
            '<p class="stamp"><span>최초 시행 <time datetime="2026-07-26">2026-07-26</time> (v1.0) · 현행 v1.2 '
            '(<time datetime="2026-11-11">2026-11-11</time> 시행)</span></p>')

    def test_two_date_en(self):
        self.assertEqual(
            legal_md.make_stamp("en", "2026-11-11", "v1.2", "2026-07-26", "v1.0"),
            '<p class="stamp"><span>First effective <time datetime="2026-07-26">2026-07-26</time> (v1.0) · Current v1.2 '
            '(effective <time datetime="2026-11-11">2026-11-11</time>)</span></p>')

    def test_single_date_unchanged(self):
        self.assertEqual(
            legal_md.make_stamp("en", "2026-11-11", "v1.0"),
            '<p class="stamp"><span>Effective <time datetime="2026-11-11">2026-11-11</time> · Version v1.0</span></p>')

    def test_stamp_line_prefixes_recognised(self):
        for ln in ("<p>시행일: x", "<p>Effective date: x", "<p>최초 시행 x", "<p>First effective x"):
            self.assertTrue(ln.startswith(legal_md.STAMP_PREFIXES), ln)


if __name__ == "__main__":
    unittest.main()
