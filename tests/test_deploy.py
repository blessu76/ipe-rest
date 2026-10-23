import re
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
WORKFLOW = (ROOT / ".github" / "workflows" / "deploy.yml").read_text(encoding="utf-8")
BUILD = ROOT / "scripts" / "build_site.sh"
KEY_FILE = re.compile(r"^[0-9a-f]{32,}\.txt$")

MUST_HAVE = ["CNAME", ".nojekyll", "robots.txt", "sitemap.xml", "llms.txt", "sw.js", "manifest.webmanifest",
             "index.html", "og-image.png", "fonts/inter-400.woff2", "go/redirects.json",
             "journal/index.html", "journal/journal.css", "journal/journal.js", "widget/ipe-engage.js", "widget/ipe-engage.css", "en/index.html", "ko/index.html"]
MUST_NOT = ["scripts", "tests", "firebase", ".github", ".git", ".gitignore", "README.md", "_site"]


class DeployWorkflow(unittest.TestCase):
    def test_uploads_built_site_not_repo_root(self):
        self.assertIn("scripts/build_site.sh _site", WORKFLOW)
        self.assertRegex(WORKFLOW, r"path:\s*'_site'")
        self.assertNotRegex(WORKFLOW, r"path:\s*'\.'")

    def test_build_script_excludes_dev_dirs(self):
        sh = BUILD.read_text(encoding="utf-8")
        for ex in ("/scripts/", "/tests/", "/.github/", "/firebase/"):
            self.assertIn("--exclude='%s'" % ex, sh)

    @unittest.skipUnless(shutil.which("rsync"), "rsync 가 PATH 에 없다 — 설치 후 다시 실행 (build_site.sh 가 rsync 를 쓴다)")
    def test_built_site_content(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "site"
            subprocess.run([str(BUILD), str(out)], check=True, capture_output=True)
            for rel in MUST_HAVE:
                if rel == "CNAME" and not (ROOT / "CNAME").exists():
                    continue  # 레포에 CNAME 이 있을 때만(Pages 설정에서 도메인 관리 시 없음)
                self.assertTrue((out / rel).exists(), "missing in _site: " + rel)
            for rel in MUST_NOT:
                self.assertFalse((out / rel).exists(), "must not ship: " + rel)
            self.assertEqual(list(out.rglob("*.md")), [])
            self.assertEqual(list(out.rglob(".DS_Store")), [])
            keys = [p for p in out.glob("*.txt") if KEY_FILE.match(p.name)]
            src_keys = [p for p in ROOT.glob("*.txt") if KEY_FILE.match(p.name)]
            self.assertTrue(keys and len(keys) == len(src_keys), "IndexNow key files must ship")

    def test_public_pages_do_not_reference_dev_dirs(self):
        pat = re.compile(r"""["'(=/ ](?:scripts|tests)/""")
        bad = []
        for p in ROOT.rglob("*"):
            rel = p.relative_to(ROOT)
            if rel.parts[0] in ("scripts", "tests", ".git", ".github", "_site") or not p.is_file():
                continue
            if p.suffix not in (".html", ".js", ".css", ".json", ".xml", ".txt", ".webmanifest"):
                continue
            if pat.search(p.read_text(encoding="utf-8", errors="ignore")):
                bad.append(str(rel))
        self.assertEqual(bad, [])


if __name__ == "__main__":
    unittest.main()
