import re
import unittest
from pathlib import Path
from urllib.parse import urlsplit, unquote

ROOT = Path(__file__).resolve().parent.parent
SW = (ROOT / "sw.js").read_text(encoding="utf-8")
DEPLOY = (ROOT / "tests" / "test_deploy.py").read_text(encoding="utf-8")
ATTR = re.compile(r"""\b(?:href|src)\s*=\s*(?:"([^"]*)"|'([^']*)')""", re.I)
SKIP_SCHEME = re.compile(r"^(?:[a-z][a-z0-9+.\-]*:|//)", re.I)

# 알려진 예외: 사이트 경로 -> 이유 (비어 있어야 정상)
KNOWN_BROKEN = {}


def must_not():
    m = re.search(r"^MUST_NOT\s*=\s*\[(.*?)\]", DEPLOY, re.M | re.S)
    return set(re.findall(r"""["']([^"']+)["']""", m.group(1)))


def deployed_html():
    # 레포 안의 *.html 전부 — MUST_NOT 최상위(scripts/ 등)와 .git 같은 점 폴더는 배포되지 않으므로 뺀다
    skip = must_not()
    pages = []
    for p in sorted(ROOT.rglob("*.html")):
        top = p.relative_to(ROOT).parts[0]
        if top in skip or top.startswith("."):
            continue
        pages.append(p)
    return pages


def site_path(ref, page):
    """href/src 값을 (사이트 경로, 쿼리) 로. 바깥·mailto·#앵커 전용은 None."""
    ref = ref.strip()
    if not ref or ref.startswith("#") or SKIP_SCHEME.match(ref):
        return None
    u = urlsplit(ref)
    path = unquote(u.path)
    if not path:
        return None
    if not path.startswith("/"):
        base = "/" + page.parent.relative_to(ROOT).as_posix() + "/"
        path = base.replace("//", "/") + path
    parts = []
    for seg in path.split("/"):
        if seg == "..":
            if parts:
                parts.pop()
        elif seg not in ("", "."):
            parts.append(seg)
    norm = "/" + "/".join(parts)
    if path.endswith("/") and norm != "/":
        norm += "/"
    return norm, u.query


def resolve(path):
    rel = path.lstrip("/")
    f = ROOT / rel
    if path.endswith("/") or f.is_dir():
        f = f / "index.html"
    return f


def refs(page):
    text = page.read_text(encoding="utf-8")
    for m in ATTR.finditer(text):
        r = site_path(m.group(1) if m.group(1) is not None else m.group(2), page)
        if r:
            yield r


class SwCoreVersions(unittest.TestCase):
    def core(self):
        m = re.search(r"const CORE = \[(.*?)\];", SW, re.S)
        self.assertTrue(m, "sw.js CORE 목록을 찾지 못했다")
        return re.findall(r"""'([^']+)'""", m.group(1))

    def test_core_assets_exist(self):
        for entry in self.core():
            path = urlsplit(entry).path
            self.assertTrue(resolve(path).is_file(), "sw.js CORE 에 있는데 파일이 없다: " + entry)

    def test_v_matches_html(self):
        want = {}
        for entry in self.core():
            u = urlsplit(entry)
            m = re.search(r"(?:^|&)v=([^&]*)", u.query)
            if m:
                want[u.path] = m.group(1)
        self.assertTrue(want, "CORE 에 ?v= 자산이 없다 — 시험이 비어 있다")
        seen = {p: set() for p in want}
        for page in deployed_html():
            for path, q in refs(page):
                if path in want:
                    m = re.search(r"(?:^|&)v=([^&]*)", q)
                    seen[path].add((m.group(1) if m else None, page.relative_to(ROOT).as_posix()))
        bad = []
        for path, v in want.items():
            for got, where in sorted(seen[path], key=str):
                if got != v:
                    bad.append("%s: sw.js ?v=%s, %s 는 ?v=%s" % (path, v, where, got))
        self.assertEqual(bad, [], "sw.js CORE 와 HTML 의 ?v= 가 다르다:\n" + "\n".join(bad[:30]))

    def test_cache_name_has_version(self):
        self.assertRegex(SW, r"const CACHE = 'ipe-v\d+';")


class InternalLinks(unittest.TestCase):
    def test_internal_links_resolve(self):
        excluded = must_not()
        self.assertIn("scripts", excluded)
        bad = {}
        pages = deployed_html()
        self.assertTrue(pages)
        for page in pages:
            for path, _q in refs(page):
                if path in KNOWN_BROKEN:
                    continue
                first = path.lstrip("/").split("/")[0]
                if first in excluded or not resolve(path).is_file():
                    bad.setdefault(path, page.relative_to(ROOT).as_posix())
        lines = ["%s  (예: %s)" % (p, w) for p, w in sorted(bad.items())]
        self.assertEqual(lines, [], "깨진 내부 링크:\n" + "\n".join(lines[:40]))


if __name__ == "__main__":
    unittest.main()
