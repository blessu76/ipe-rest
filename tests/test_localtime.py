import hashlib
import shutil
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
JS = ROOT / "shared" / "ipe-localtime.js"
SHA = ROOT / "shared" / "ipe-localtime.sha256"
HEAD = "/* ipe-localtime v1 · 정본 ipe-rest/shared/ipe-localtime.js · 사본은 바이트 그대로 */"


class LocalTime(unittest.TestCase):
    def test_file_shape(self):
        raw = JS.read_bytes()
        raw.decode("utf-8")
        self.assertNotIn(b"\r", raw)
        self.assertLessEqual(len(raw), 4096)
        self.assertNotIn(b"</script", raw.lower())

    def test_header_v1(self):
        self.assertEqual(JS.read_text(encoding="utf-8").split("\n", 1)[0], HEAD)

    def test_sha256_matches(self):
        want = SHA.read_text(encoding="utf-8").split()[0]
        self.assertEqual(hashlib.sha256(JS.read_bytes()).hexdigest(), want)

    @unittest.skipUnless(shutil.which("node"), "node 없음")
    def test_node_syntax(self):
        r = subprocess.run(["node", "--check", str(JS)], capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stderr)


if __name__ == "__main__":
    unittest.main()
