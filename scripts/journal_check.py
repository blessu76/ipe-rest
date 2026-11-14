#!/usr/bin/env python3
"""Journal copy-review gate (Iris) — wired into scripts/check.sh.

Posts published on or before 2026-11-14 are grandfathered: <meta name="ipe:copy-review" content="legacy-2026-11-14">.
Posts from 2026-11-15 on must pass the kit's journal.assert_publishable: all 12 language editions present and
copy_review = iris + ipe:copy-review-date (YYYY-MM-DD). The legacy value is NOT accepted for them.
Usage: python3 scripts/journal_check.py   (exit 1 on any problem)
"""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "vendor"))
from ipe_web_kit import journal as KJ, languages  # noqa: E402

LEGACY = "legacy-2026-11-14"
CUTOFF = "2026-11-14"


def meta(src, name):
    m = re.search(r'<meta name="%s" content="([^"]*)"' % re.escape(name), src)
    return m.group(1) if m else ""


def problems(src_dir=None, i18n_dir=None):
    src_dir = Path(src_dir or ROOT / "scripts" / "journal_src")
    i18n_dir = Path(i18n_dir or ROOT / "scripts" / "journal_i18n")
    out, new = [], {}
    for f in sorted(src_dir.glob("2026-*.html")):
        slug = f.stem
        date = slug[:10]
        src = f.read_text(encoding="utf-8")
        review = meta(src, "ipe:copy-review")
        if date <= CUTOFF:
            if review not in (LEGACY, "iris"):
                out.append("%s: ipe:copy-review 가 %s 또는 iris 여야 한다 (현재 %r)" % (slug, LEGACY, review))
            continue
        if review == LEGACY:
            out.append("%s: %s 로 면제되는 것은 %s 이전 글뿐이다" % (slug, LEGACY, CUTOFF))
            continue
        rdate = meta(src, "ipe:copy-review-date")
        editions = {}
        for l in languages.SUPPORTED:
            if l in ("en", "ko") or (i18n_dir / slug / ("%s.json" % l)).is_file():
                editions[l] = {"url": "/journal/%s/%s/" % (l, slug), "copy_review": review, "copy_review_date": rdate}
        new[slug] = editions
    for slug, ed in new.items():
        for p in KJ.check_post(ed):
            out.append("%s: %s" % (slug, p))
    return out


if __name__ == "__main__":
    bad = problems()
    for b in bad:
        print("journal_check: " + b)
    print("journal_check: %s" % ("FAIL (%d)" % len(bad) if bad else "ok"))
    sys.exit(1 if bad else 0)
