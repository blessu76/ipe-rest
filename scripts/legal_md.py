#!/usr/bin/env python3
"""Convert the legal source Markdown (v1.0, ipe-studio site/legal/*.md) into scripts/legal_src/<page>.<lang>.html.

Only the <main> body is regenerated; the page head / header / footer of each legal_src file are kept (the first run for
terms.ko derives them from privacy.ko). The text is converted 1:1 (headings, lists, tables, links, bold, code) — no wording
edits. The only text removals are the publishing-notice blockquote lines at the top of each source and the sentence about
the mailbox two-step verification (unconfirmed claim), both listed in REMOVE below.

Usage: python3 scripts/legal_md.py [--src DIR]   (default DIR = ~/Developer/_ipe/site/legal)
"""
import argparse
import html
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "scripts" / "legal_src"
DEFAULT_SRC = Path.home() / "Developer" / "_ipe" / "site" / "legal"

# (page, lang) -> (h1 first part, h1 <em> part)
TITLE = {("privacy", "en"): ("Privacy ", "policy."), ("privacy", "ko"): ("개인정보 ", "처리방침."),
         ("terms", "en"): ("Terms of ", "use."), ("terms", "ko"): ("이용", "약관.")}
EYEBROW = {"privacy": "privacy", "terms": "terms"}
BACK = {"en": ("/en/", "← back to ipe.rest"), "ko": ("/ko/", "← ipe.rest 로 돌아가기")}

# Sentence fragments removed from table cells / lines (nothing else is ever cut).
REMOVE = (" 문의 메일 계정 보호 `[확인 필요: 2단계 인증 적용 확인]`", " Mailbox account protection `[confirm: two-step verification in place]`")

CANDIDATE = (("v1.0(후보)", "v1.0"), ("v1.0 (candidate)", "v1.0"))


def inline(s):
    s = html.escape(s, quote=False)
    s = re.sub(r"`([^`]+)`", r"<code>\1</code>", s)
    s = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", s)

    def link(m):
        href = m.group(2)
        if href in ("/privacy/", "/terms/"):  # internal: same-language canonical (rewritten to /legal/… at build)
            return '<a href="%s">%s</a>' % (LANG_PREFIX[0] + href, m.group(1))
        return '<a href="%s" target="_blank" rel="noopener">%s</a>' % (href, m.group(1))
    return re.sub(r"\[([^\]]+)\]\(([^)]+)\)", link, s)


LANG_PREFIX = ["/en"]


def cells(row):
    row = row.strip()
    assert row.startswith("|") and row.endswith("|"), row
    return [c.strip() for c in row[1:-1].split("|")]


def convert(md, lang):
    """-> (h1 text, intro stamp line or None, body html)."""
    LANG_PREFIX[0] = "/" + lang
    for r in REMOVE:
        md = md.replace(r, "")
    for a, b in CANDIDATE:  # "v1.0 (candidate)" -> "v1.0" (published version; version-table row included)
        md = md.replace(a, b)
    lines = md.split("\n")
    out, i, h1 = [], 0, None
    while i < len(lines):
        ln = lines[i]
        if not ln.strip():
            i += 1
        elif ln.startswith("# ") and h1 is None:
            h1 = ln[2:].strip()
            i += 1
        elif ln.startswith("# "):  # appendix headings
            out.append("<h2>%s</h2>" % inline(ln[2:].strip()))
            i += 1
        elif ln.startswith("## "):
            out.append("<h2>%s</h2>" % inline(ln[3:].strip()))
            i += 1
        elif ln.strip() == "---":
            out.append("<hr>")
            i += 1
        elif ln.startswith(">"):
            blk = []
            while i < len(lines) and lines[i].startswith(">"):
                blk.append(lines[i][1:].strip())
                i += 1
            out.append(("BQ", blk))
        elif ln.startswith("|"):
            rows = []
            while i < len(lines) and lines[i].startswith("|"):
                rows.append(lines[i])
                i += 1
            head, body = cells(rows[0]), [cells(r) for r in rows[2:]]
            t = ['<div class="tbl"><table>', "<thead><tr>%s</tr></thead>" % "".join("<th>%s</th>" % inline(c) for c in head), "<tbody>"]
            t += ["<tr>%s</tr>" % "".join("<td>%s</td>" % inline(c) for c in r) for r in body]
            t += ["</tbody>", "</table></div>"]
            out.append("\n".join(t))
        elif ln.startswith("- ") or re.match(r"\d+\. ", ln):
            ordered = not ln.startswith("- ")
            items = []
            while i < len(lines) and (lines[i].startswith("- ") if not ordered else re.match(r"\d+\. ", lines[i])):
                items.append(re.sub(r"^(- |\d+\. )", "", lines[i]))
                i += 1
            tag = "ol" if ordered else "ul"
            out.append("<%s>\n%s\n</%s>" % (tag, "\n".join("  <li>%s</li>" % inline(x) for x in items), tag))
        else:
            para = [ln]
            i += 1
            while i < len(lines) and lines[i].strip() and not re.match(r"(#|\||- |\d+\. |>|---)", lines[i]):
                para.append(lines[i])
                i += 1
            out.append("<p>%s</p>" % inline("\n".join(para)))
    return h1, out


def render_main(page, lang, md, stamp_fn, drop_bq):
    h1, blocks = convert(md, lang)
    body, stamp = [], None
    for b in blocks:
        if isinstance(b, tuple):  # blockquote: the first lines are the pre-publish notice; keep the substantive rest
            for ln in b[1]:
                if ln in drop_bq:
                    continue
                body.append("<p>%s</p>" % inline(ln))
            continue
        body.append(b)
    pre, em = TITLE[(page, lang)]
    back_href, back_txt = BACK[lang]
    body = stamp_fn(body)
    ind = "\n".join("    " + x.replace("\n", "\n    ") for x in body)
    return ('<main id="main">\n<div class="wrap">\n  <p class="eyebrow"><i></i><span class="ltr">%s</span></p>\n'
            '  <h1 class="page-title">%s<em>%s</em></h1>\n\n  <div class="prose">\n%s\n  </div>\n\n'
            '  <a class="back" href="%s"><span>%s</span></a>\n</div>\n</main>' % (EYEBROW[page], pre, em, ind, back_href, back_txt))


TBL_CSS = (".prose hr{border:0;border-top:1px solid var(--line);margin:48px 0}\n"
           ".prose ol{margin:0 0 26px;padding-inline-start:1.5em;font-size:17px;line-height:1.8}\n"
           ".tbl{margin:0 0 26px;overflow-x:auto;-webkit-overflow-scrolling:touch}\n"
           ".prose table{border-collapse:collapse;min-width:100%;font:400 14px/1.6 var(--sans);color:var(--text)}\n"
           ".prose th,.prose td{padding:8px 12px;border:1px solid var(--hair);text-align:start;vertical-align:top;overflow-wrap:anywhere}\n"
           ".prose th{color:var(--ink);font-weight:600;background:var(--tint);white-space:nowrap}\n"
           ".prose td{min-width:8em}\n")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", default=str(DEFAULT_SRC))
    ap.add_argument("--effective", required=True, help="effective date YYYY-MM-DD, as decided by the owner")
    ap.add_argument("--version", default="v1.0")
    a = ap.parse_args()
    src = Path(a.src)
    for page, lang in (("privacy", "en"), ("privacy", "ko"), ("terms", "en"), ("terms", "ko")):
        tpl = OUT / ("%s.%s.html" % (page, lang))
        if not tpl.exists():  # terms.ko: head/header/footer from privacy.ko with the page name swapped
            tpl = OUT / "privacy.ko.html"
        t = tpl.read_text(encoding="utf-8")
        i, j = t.index('<main id="main">'), t.index("</main>") + len("</main>")
        head, tail = t[:i], t[j:]
        if (page, lang) == ("terms", "ko") and tpl.name == "privacy.ko.html":
            head = head.replace("/privacy/", "/terms/").replace("개인정보처리방침", "이용약관")
            head = re.sub(r'<meta name="description" content="[^"]*">', '<meta name="description" content="ipe.rest 와 모든 하위 도메인·모바일 앱 이용약관: 이용 방법, 콘텐츠 권리, 유료 기능과 인앱결제, 광고·제3자 링크, 책임의 한계.">', head)
            head = re.sub(r'(<meta property="og:description"|<meta name="twitter:description") content="[^"]*">',
                          r'\1 content="ipe.rest 와 모든 하위 도메인·모바일 앱 이용약관: 이용 방법, 콘텐츠 권리, 유료 기능과 인앱결제, 광고·제3자 링크, 책임의 한계.">', head)
            head = re.sub(r'(?:<link rel="alternate" hreflang="(?!x-default|en|ko)[^"]+" href="[^"]+">\n)+', "", head)
            head = re.sub(r'(<meta property="og:locale:alternate" content="[^"]+">\n)+', '<meta property="og:locale:alternate" content="en_US">\n', head)
            head = re.sub(r'"name": "privacy"', '"name": "terms"', head)
            head = re.sub(r'(<select[^>]*>)(.*?)(</select>)', lambda m: m.group(1) + '\n      <option value="/en/terms/" lang="en">EN</option>\n      <option value="/ko/terms/" lang="ko" selected>KO</option>\n    ' + m.group(3), head, flags=re.S)
            tail = tail.replace('href="/en/terms/" hreflang="en">terms<', 'href="/ko/terms/" hreflang="ko">이용약관<')
        elif page == "terms" and lang == "en":  # en terms now has a ko sibling: hreflang + picker
            if 'hreflang="ko"' not in head:
                head = head.replace('<link rel="alternate" hreflang="en" href="https://ipe.rest/en/terms/">\n',
                                    '<link rel="alternate" hreflang="en" href="https://ipe.rest/en/terms/">\n<link rel="alternate" hreflang="ko" href="https://ipe.rest/ko/terms/">\n')
                head = head.replace('<option value="/en/terms/" lang="en" selected>EN</option>\n',
                                    '<option value="/en/terms/" lang="en" selected>EN</option>\n      <option value="/ko/terms/" lang="ko">KO</option>\n')
        if ".tbl{" not in head:
            head = head.replace("</style>", TBL_CSS + "</style>")
        md = (src / ("%s.%s.md" % (page, lang))).read_text(encoding="utf-8")
        drop = [x for x in md.split("\n") if x.startswith(">") and ("v1.0 후보" in x or "v1.0 candidate" in x or "[확인 필요: …]" in x or "[confirm: …]" in x)]
        drop = [x[1:].strip() for x in drop]

        def stamp(body, lang=lang):
            for k, b in enumerate(body):
                if (b.startswith("<p>시행일: ") or b.startswith("<p>Effective date: ")):
                    label = "시행일" if lang == "ko" else "Effective"
                    body[k] = '<p class="stamp"><span>%s <time datetime="%s">%s</time> · %s %s</span></p>' % (
                        label, a.effective, a.effective, "버전" if lang == "ko" else "Version", a.version)
            return body
        # blank-line-less notice lines that are "kept" (they are real text) go through unchanged
        (OUT / ("%s.%s.html" % (page, lang))).write_text(head + render_main(page, lang, md, stamp, drop) + tail, encoding="utf-8")
        print("wrote", "%s.%s.html" % (page, lang))


if __name__ == "__main__":
    main()
