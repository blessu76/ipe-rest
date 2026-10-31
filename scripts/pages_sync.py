#!/usr/bin/env python3
"""Generate the ipe.rest info pages (about / contact / privacy) in 12 languages — stdlib only.

Sources:  scripts/pages_src/<page>.html            hand-written EN+KO source (not served)
          scripts/pages_i18n/<page>/<lang>.json    10 AI translations: {"title", "description", "main"}  (main = the HTML
                                                   between <div class="wrap"> and its closing </div>, same structure as the EN page)
Writes:   /<lang>/<page>/index.html                single-language static pages (en/ko from the source; 10 more where a JSON exists)
          /<page>/index.html                       language-chooser shell (language-less): canonical + hreflang x-default -> /en/<page>/,
                                                   NOT in the sitemap, no noindex (same rule as the journal shells; see README-journal.md)
          sitemap.xml  <!-- pages:start/end -->    every language page (not the shell): lastmod + hreflang (x-default = /en/) + image
          llms.txt     <!-- pages:llms:start/end -->

In `main`, links /about/ /contact/ /privacy/ and the back link "/" are rewritten to the page's own language.
Never edit the generated files by hand.   Usage: python3 scripts/pages_sync.py [--check]
"""
import argparse
import html
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import journal_i18n as J  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
SITE = J.SITE
LANGS = J.LANGS
TR = J.TR_LANGS
PAGES = ("about", "contact", "privacy")
LASTMOD = "2026-10-22"
LD_TYPE = {"about": "AboutPage", "contact": "ContactPage", "privacy": "WebPage"}
esc = J.esc


def page_url(page, lang=None):
    return "%s/%s/" % (SITE, page) if lang is None else "%s/%s/%s/" % (SITE, lang, page)


def meta(src, name):
    m = re.search(r'<meta name="%s" content="([^"]*)"' % re.escape(name), src)
    return html.unescape(m.group(1)) if m else None


def split_source(src, lang):
    """EN or KO single-language title/description/main from the bilingual source."""
    other = "ko" if lang == "en" else "en"
    i = src.index('<div class="wrap">') + len('<div class="wrap">')
    j = src.index("\n</div>\n</main>")
    main = src[i:j]
    main = re.sub(r'<div class="prose" lang="%s">.*?\n  </div>\n' % other, "", main, flags=re.S)
    main = re.sub(r'<(span|h1|p) ([^>]*)lang="%s"[^>]*>.*?</\1>\n?' % other, "", main, flags=re.S)
    main = main.replace(' lang="%s"' % lang, "")
    main = re.sub(r"\n{3,}", "\n\n", main)
    if lang == "en":
        title, desc = meta(src, "ipe:title-en"), meta(src, "description")
    else:
        title, desc = meta(src, "ipe:title-ko"), meta(src, "ipe:description-ko")
    return {"title": title, "description": desc, "main": main}


def load():
    srcs, data = {}, {}
    for p in PAGES:
        s = (ROOT / "scripts" / "pages_src" / (p + ".html")).read_text(encoding="utf-8")
        srcs[p] = s
        data[p] = {l: split_source(s, l) for l in J.ORIG_LANGS}
        for l in TR:
            f = ROOT / "scripts" / "pages_i18n" / p / (l + ".json")
            if f.exists():
                data[p][l] = json.loads(f.read_text(encoding="utf-8"))
    ui = json.loads((ROOT / "scripts" / "journal_i18n" / "ui.json").read_text(encoding="utf-8"))
    return data, ui


def langs_of(data, p):
    return [l for l in LANGS if l in data[p]]


def cluster(data, p):
    """x-default = the /en/ page, never the language-less shell (Search Console picked the shell over /en/ on the journal)."""
    return [("x-default", page_url(p, "en"))] + [(l, page_url(p, l)) for l in langs_of(data, p)]


def localize(main, lang):
    """Point internal links at the page's own language (translations may carry the EN-localized hrefs)."""
    main = re.sub(r'href="/(?:[a-z]{2}/)?(about|contact|privacy)/"', lambda m: 'href="/%s/%s/"' % (lang, m.group(1)), main)
    main = re.sub(r'href="/journal/(?:[a-z]{2}/)?"', 'href="/journal/%s/"' % lang, main)
    main = re.sub(r'class="back" href="/(?:[a-z]{2}/)?"', 'class="back" href="/%s/"' % lang, main)
    return main


def check_data(p, lang, d):
    errs = []
    for k in ("title", "description", "main"):
        if not d.get(k):
            errs.append("%s/%s: missing %s" % (p, lang, k))
    if d.get("main"):
        for needle in ("mailto:ipe.haven@gmail.com",) if p != "privacy" else ("ipe_lang",):
            if needle not in d["main"]:
                errs.append("%s/%s: main lacks %s" % (p, lang, needle))
        if "<h1" not in d["main"] or 'class="back"' not in d["main"]:
            errs.append("%s/%s: main lacks h1/back link" % (p, lang))
    return errs


def render(p, lang, data, ui):
    u = ui[lang]
    d = data[p][lang]
    url = page_url(p, lang)
    cl = cluster(data, p)
    main = localize(d["main"], lang)
    if lang in TR:
        note = '  <p class="ai-note" role="note"><strong>%s</strong> %s <a href="%s" hreflang="en">%s</a></p>' % (
            esc(u["ai_label"]), esc(u["ai_text"]), "/en/%s/" % p, esc(u["ai_link"]))
        main, n = re.subn(r'(<p class="(?:lede|stamp)"[^>]*>.*?</p>\n)', lambda m: m.group(1) + note + "\n", main, count=1, flags=re.S)
        if n != 1:
            main, n = re.subn(r"(</h1>\n)", lambda m: m.group(1) + note + "\n", main, count=1)
    alts = "\n".join('<meta property="og:locale:alternate" content="%s">' % J.OG_LOCALE[l] for l in langs_of(data, p) if l != lang)
    ld = {"@context": "https://schema.org", "@graph": [
        {"@type": LD_TYPE[p], "@id": url + "#webpage", "name": d["title"], "url": url, "inLanguage": lang,
         "isPartOf": {"@id": SITE + "/%s/#website" % lang}},
        {"@type": "BreadcrumbList", "@id": url + "#breadcrumb", "itemListElement": [
            {"@type": "ListItem", "position": 1, "name": "ipe()", "item": SITE + "/%s/" % lang},
            {"@type": "ListItem", "position": 2, "name": u[p], "item": url}]}]}
    parts = ['<!DOCTYPE html>', '<html lang="%s" dir="%s">' % (lang, "rtl" if lang in J.RTL else "ltr"), '<head>',
             J._common_head(lang, d["title"], d["description"], url),
             "\n".join('<link rel="alternate" hreflang="%s" href="%s">' % (h, x) for h, x in cl),
             J._assets_head(), '',
             '<meta property="og:type" content="website">', '<meta property="og:site_name" content="ipe()">',
             '<meta property="og:title" content="%s">' % esc(d["title"]),
             '<meta property="og:description" content="%s">' % esc(d["description"]),
             '<meta property="og:url" content="%s">' % url,
             '<meta property="og:image" content="%s/og-image.png">' % SITE,
             '<meta property="og:image:width" content="1200">', '<meta property="og:image:height" content="630">',
             '<meta property="og:image:alt" content="%s">' % J.OG_IMAGE_ALT_ATTR,
             '<meta property="og:locale" content="%s">' % J.OG_LOCALE[lang], alts,
             '<meta name="twitter:card" content="summary_large_image">',
             '<meta name="twitter:title" content="%s">' % esc(d["title"]),
             '<meta name="twitter:description" content="%s">' % esc(d["description"]),
             '<meta name="twitter:image" content="%s/og-image.png">' % SITE,
             '<meta name="twitter:image:alt" content="%s">' % J.OG_IMAGE_ALT_ATTR,
             J.ld_script(ld), J.css_inline(), '</head>', '<body>',
             J._header(u, lang, cl), '', '<main id="main">', '<div class="wrap">' + main, '</div>', '</main>', '',
             J._footer(u, lang), '<script src="/journal/journal.js?v=%s" defer></script>' % J.VER_JS, '</body>', '</html>', '']
    return "\n".join(parts)


def render_chooser(p, data, ui):
    langs = langs_of(data, p)
    en = data[p]["en"]
    url = page_url(p, "en")  # canonical / og:url / JSON-LD url -> the /en/ page (the shell itself is /<page>/ and deliberately has NO noindex)
    page = {"@context": "https://schema.org", "@type": LD_TYPE[p], "@id": url + "#webpage", "url": url, "name": en["title"],
            "description": en["description"], "inLanguage": "en", "isPartOf": {"@id": SITE + "/#website"}}
    rows = [(l, page_url(p, l), data[p][l]["title"]) for l in langs]
    cl = cluster(data, p)
    head = J._chooser_head(en["title"], en["description"], url, cl, "website", "en_US", [page])
    body = J._chooser_body(en["title"], "ipe() — " + ", ".join(J.NATIVE[l] for l in langs), rows, dict(ui["en"], eyebrow=ui["en"][p]), "en", cl)
    return "\n".join(head) + "\n" + body


def sitemap_block(data):
    out = ["  <!-- pages:start -->"]
    for p in PAGES:
        for lang in langs_of(data, p):  # the language-less shell /<page>/ is NOT listed (canonical -> /en/)
            out += ["  <url>", "    <loc>%s</loc>" % page_url(p, lang), "    <lastmod>%s</lastmod>" % LASTMOD,
                    "    <changefreq>yearly</changefreq>", "    <priority>%s</priority>" % ("0.5" if lang == "en" else "0.4")]
            out += ['    <xhtml:link rel="alternate" hreflang="%s" href="%s"/>' % (h, x) for h, x in cluster(data, p)]
            out += ["    <image:image><image:loc>%s/og-image.png</image:loc></image:image>" % SITE, "  </url>"]
    out.append("  <!-- pages:end -->")
    return "\n".join(out)


def llms_block(data):
    lines = ["<!-- pages:llms:start -->"]
    desc = {"about": "who runs ipe() (Davy Kim, ipe Studio, Seoul) and what the studio does",
            "contact": "ipe.haven@gmail.com (replies within 10 days)",
            "privacy": "Google Analytics, language preference stored in the browser, email correspondence, how to request access or deletion; no ads on ipe.rest"}
    for p in PAGES:
        lines.append("- %s (12 languages, one static page per language): %s — %s" % (p.capitalize(), page_url(p, "en"), desc[p]))
        lines += ["  - %s [%s]%s: %s" % (J.NATIVE[l], l, " (AI translation)" if l in TR else "", page_url(p, l)) for l in langs_of(data, p)]
    lines.append("<!-- pages:llms:end -->")
    return "\n".join(lines)


def between_replace(text, start, end, block):
    i = text.index(start)
    return text[:i] + block + text[text.index(end) + len(end):]


def build():
    data, ui = load()
    writes, errors = {}, []
    for p in PAGES:
        for l in langs_of(data, p):
            errors += check_data(p, l, data[p][l])
            writes[ROOT / l / p / "index.html"] = render(p, l, data, ui)
        writes[ROOT / p / "index.html"] = render_chooser(p, data, ui)
    sm = (ROOT / "sitemap.xml").read_text(encoding="utf-8")
    if "<!-- pages:start -->" not in sm:  # first run: replace the three hand-written <url> entries
        sm = re.sub(r'  <url>\n    <loc>https://ipe\.rest/(?:about|contact|privacy)/</loc>.*?</url>\n', "", sm, flags=re.S)
        sm = sm.replace("</urlset>", "  <!-- pages:start -->\n  <!-- pages:end -->\n</urlset>")
    writes[ROOT / "sitemap.xml"] = between_replace(sm, "  <!-- pages:start -->", "<!-- pages:end -->", sitemap_block(data))
    lt = (ROOT / "llms.txt").read_text(encoding="utf-8")
    if "<!-- pages:llms:start -->" not in lt:
        lt = re.sub(r"- About: [^\n]*\n- Contact: [^\n]*\n- Privacy policy: [^\n]*\n", "<!-- pages:llms:start -->\n<!-- pages:llms:end -->\n", lt, count=1)
    writes[ROOT / "llms.txt"] = between_replace(lt, "<!-- pages:llms:start -->", "<!-- pages:llms:end -->", llms_block(data))
    return writes, errors


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true")
    a = ap.parse_args()
    writes, errors = build()
    for e in errors:
        print("ERROR", e)
    if errors:
        return 1
    stale = [p for p, t in writes.items() if not p.exists() or p.read_text(encoding="utf-8") != t]
    if a.check:
        for p in stale:
            print("out of date:", p.relative_to(ROOT))
        return 1 if stale else 0
    for p in stale:
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(writes[p], encoding="utf-8")
    print("pages_sync: %d file(s) updated" % len(stale))
    return 0


if __name__ == "__main__":
    sys.exit(main())
