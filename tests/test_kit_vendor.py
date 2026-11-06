"""Web kit (vendor/ipe_web_kit) — the copy is untouched, pinned to a tag, and wired into the builders."""
import hashlib
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
import indexnow  # noqa: E402
import journal_i18n as J  # noqa: E402
from ipe_web_kit import __version__ as KIT_VERSION, localtime, seo  # noqa: E402  (journal_i18n puts vendor/ on sys.path)


class KitVendor(unittest.TestCase):
    def test_vendor_copy_is_unmodified(self):
        r = subprocess.run([sys.executable, str(ROOT / "vendor" / "ipe_web_kit" / "vendor.py"), "verify", str(ROOT)],
                           capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)

    def test_pinned_tag(self):
        stamp = (ROOT / "vendor" / "ipe_web_kit" / "KIT_VERSION").read_text(encoding="utf-8").split()
        self.assertEqual(stamp[0], "v" + KIT_VERSION)
        self.assertRegex(stamp[1], r"^[0-9a-f]{40}$")

    def test_imports_come_from_vendor(self):
        vendor = str((ROOT / "vendor").resolve())
        for mod in (seo, localtime):
            self.assertTrue(str(Path(mod.__file__).resolve()).startswith(vendor), mod.__file__)
        self.assertEqual(indexnow.find_key.__module__, "ipe_web_kit.indexnow")
        self.assertIs(J.esc, seo.esc)
        self.assertEqual(J.ORG_ID, seo.ORG_ID)

    def test_kit_localtime_is_the_canonical_shared_copy(self):
        # ipe-rest/shared is the 정본: change it there first, then cut a new kit tag and vendor update
        shared = (ROOT / "shared" / "ipe-localtime.js").read_bytes()
        self.assertEqual(localtime.LOCALTIME_JS.read_bytes(), shared)
        self.assertEqual(localtime.LOCALTIME_SHA256, (ROOT / "shared" / "ipe-localtime.sha256").read_text().split()[0])
        self.assertEqual(J.localtime_script(), "<script>" + shared.decode("utf-8") + "</script>")
        self.assertEqual(hashlib.sha256(shared).hexdigest(), localtime.LOCALTIME_SHA256)


if __name__ == "__main__":
    unittest.main()
