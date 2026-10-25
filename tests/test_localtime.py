import hashlib
import json
import os
import shutil
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
JS = ROOT / "shared" / "ipe-localtime.js"
SHA = ROOT / "shared" / "ipe-localtime.sha256"
HEAD = "/* ipe-localtime v2 · 정본 ipe-rest/shared/ipe-localtime.js · 사본은 바이트 그대로 */"


class LocalTime(unittest.TestCase):
    def test_file_shape(self):
        raw = JS.read_bytes()
        raw.decode("utf-8")
        self.assertNotIn(b"\r", raw)
        self.assertLessEqual(len(raw), 4096)
        low = raw.lower()
        for bad in (b"</script", b"<script", b"<!--"):
            self.assertNotIn(bad, low)

    def test_header_v2(self):
        self.assertEqual(JS.read_text(encoding="utf-8").split("\n", 1)[0], HEAD)

    def test_sha256_matches(self):
        want = SHA.read_text(encoding="utf-8").split()[0]
        self.assertEqual(hashlib.sha256(JS.read_bytes()).hexdigest(), want)

    @unittest.skipUnless(shutil.which("node"), "node 없음")
    def test_node_syntax(self):
        r = subprocess.run(["node", "--check", str(JS)], capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stderr)

    def run_js(self, tz, lang, items):
        """items: [datetime 속성 또는 None] -> [(text, title, done)]"""
        harness = (
            "var items=%s.map(function(dt){var a={};if(dt!==null)a.datetime=dt;"
            "return {t:'STATIC',a:a,hasAttribute:function(k){return k in this.a},"
            "getAttribute:function(k){return k in this.a?this.a[k]:null},"
            "setAttribute:function(k,v){this.a[k]=v},"
            "get textContent(){return this.t},set textContent(v){this.t=v}};});"
            "global.document={documentElement:{lang:%s},querySelectorAll:function(){return items}};"
            "var src=require('fs').readFileSync(%s,'utf8');"
            "eval(src);eval(src);"
            "console.log(JSON.stringify(items.map(function(e){return [e.t,e.a.title||null,'data-ipe-time-done' in e.a]})));"
        ) % (json.dumps(items), json.dumps(lang), json.dumps(str(JS)))
        env = dict(os.environ, TZ=tz)
        r = subprocess.run(["node", "-e", harness], capture_output=True, text=True, env=env)
        self.assertEqual(r.returncode, 0, r.stderr)
        return json.loads(r.stdout)

    @unittest.skipUnless(shutil.which("node"), "node 없음")
    def test_converts_by_zone_once(self):
        for off in ("+09:00", "+0900"):
            la = self.run_js("America/Los_Angeles", "en", ["2026-10-25T11:30" + off])[0]
            self.assertIn("Oct 24", la[0])
            self.assertIn("19:30", la[0])
            self.assertEqual(la[1], "STATIC")  # 한 번만 바뀜(두 번 실행해도 title 이 변환문으로 덮이지 않음)
            self.assertTrue(la[2])
            kr = self.run_js("Asia/Seoul", "en", ["2026-10-25T11:30" + off])[0]
            self.assertIn("Oct 25", kr[0])
            self.assertIn("11:30", kr[0])
            self.assertIn("KST", kr[0])
        z = self.run_js("Asia/Seoul", "en", ["2026-10-25T02:30:00Z"])[0]
        self.assertIn("11:30", z[0])

    @unittest.skipUnless(shutil.which("node"), "node 없음")
    def test_invalid_or_offsetless_left_alone(self):
        bad = ["2026-10-25T11:30", "2026-10-25", "garbage", "", "2026-10-25 11:30+09:00", None]
        for row in self.run_js("America/Los_Angeles", "en", bad):
            self.assertEqual(row, ["STATIC", None, False])

    @unittest.skipUnless(shutil.which("node"), "node 없음")
    def test_gregorian_latin_digits(self):
        for lang in ("th", "fa", "ar", "hi"):
            t = self.run_js("Asia/Seoul", lang, ["2026-10-25T11:30+09:00"])[0][0]
            self.assertRegex(t, r"2026", lang)
            self.assertRegex(t, r"11:30", lang)
            self.assertNotRegex(t, r"[٠-٩۰-۹०-९๐-๙]", lang)
            self.assertNotIn("2569", t, lang)  # th 불기
            self.assertNotIn("1405", t, lang)  # fa 페르시아력


if __name__ == "__main__":
    unittest.main()
