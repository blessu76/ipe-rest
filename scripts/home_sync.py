#!/usr/bin/env python3
"""Generate the ipe.rest main page in 12 languages — stdlib only (Python 3.8+).

Source:   scripts/home_src/index.html      page template (English markup + data-i18n keys, <!-- home:* --> markers)
          scripts/home_i18n/<lang>.json    UI strings per language (en is the fallback for missing keys)
Writes:   /<lang>/index.html               12 single-language static pages (self-canonical, hreflang 12 + x-default)
          /index.html                      x-default language chooser (self-canonical; never auto-redirects crawlers)
          sitemap.xml  <!-- home:start/end -->        13 urls (root + 12) with lastmod + hreflang 13 + image
          llms.txt     <!-- home:llms:start/end -->   main page per language

Never edit /index.html or /<lang>/index.html by hand. `?lang=xx` is retired: old links land on / (or a page) and a small
script forwards them to /xx/.

Usage:
    python3 scripts/home_sync.py           # rewrite
    python3 scripts/home_sync.py --check   # exit 1 if anything is out of date
"""
import argparse
import html
import json
import re
import sys
from html.parser import HTMLParser
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import journal_i18n as J  # noqa: E402
import journal_sync as JS  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
SITE = J.SITE
LANGS = J.LANGS
RTL = J.RTL
OG_LOCALE = J.OG_LOCALE
NATIVE = J.NATIVE
LASTMOD = "2026-10-22"  # fallback only: build() uses the newest journal post date (the cards change with it)


def home_url(lang=None):
    return SITE + "/" if lang is None else "%s/%s/" % (SITE, lang)


def esc(s):
    return html.escape(s, quote=True)


def load(root=ROOT):
    src = (root / "scripts" / "home_src" / "index.html").read_text(encoding="utf-8")
    ui = {l: json.loads((root / "scripts" / "home_i18n" / (l + ".json")).read_text(encoding="utf-8")) for l in LANGS}
    jui = json.loads((root / "scripts" / "journal_i18n" / "ui.json").read_text(encoding="utf-8"))
    for l in LANGS:  # the journal UI file already has a translated "journal" label for all 12 languages
        ui[l].setdefault("nav_journal", jui[l]["journal"])
    global jui_ai
    jui_ai = jui
    return src, ui


jui_ai = {}
CARDS = 3  # newest journal posts shown on the main page


def journal_posts(root=ROOT):
    """[(post, {lang: data})] newest first — the same sources and translations the journal pages are generated from."""
    sdir = root / "scripts" / "journal_src"
    _ui, tr, _errs = J.load(root)
    out = []
    for f in sorted((f for f in sdir.glob("*.html") if JS.DIR_RE.match(f.stem)), key=lambda f: f.stem, reverse=True):
        p, errs = JS.load_post(f, root)
        if errs or "langdata" not in p:
            raise SystemExit("home_sync: journal post %s is invalid — run journal_sync.py first" % f.stem)
        data = dict(p["langdata"])
        data.update(tr.get(p["slug"], {}))
        out.append((p, data))
    return out


def journal_section(posts, lang, jui_l, d):
    """Static '03 journal' card section: the newest CARDS posts that exist in `lang`. Hidden section = no markup at all."""
    order = {p["slug"]: i + 1 for i, (p, _d) in enumerate(reversed(posts))}  # J-nn = publication order, stable as posts are added
    items = [(p, data[lang]) for p, data in posts if lang in data][:CARDS]
    if not items:
        return ""
    read = jui_l["read"]
    cards = []
    for p, x in items:
        cards.append(
            '      <li class="jcard">\n'
            '        <p class="jcard-meta"><span class="jcard-no ltr" aria-hidden="true">J-%02d</span>%s · <span class="ltr">%s</span></p>\n'
            '        <h3><a class="jcard-link" href="/journal/%s/%s/">%s</a></h3>\n'
            '        <p class="jcard-ex">%s</p>\n'
            '        <span class="jcard-act" aria-hidden="true">%s</span>\n'
            '        <span class="mk" aria-hidden="true"></span>\n'
            '      </li>' % (order[p["slug"]], J.time_tag(*J.stamp(p)), esc(p["category"]), lang, p["slug"],
                           html.escape(x["title"], quote=False), html.escape(x["excerpt"], quote=False), esc(read)))
    return ('  <section class="sec wrap" id="journal" aria-labelledby="journal-h">\n'
            '    <div class="sec-head">\n'
            '      <span class="sec-no ltr" aria-hidden="true">03</span>\n'
            '      <h2 class="sec-label" id="journal-h">%s</h2>\n'
            '      <a class="text-link sec-cap" href="/journal/%s/"><span>%s</span> <span class="arw ltr" aria-hidden="true">→</span></a>\n'
            '    </div>\n'
            '    <!-- journal:home:start (generated — do not hand-edit) -->\n'
            '    <ul class="jcards">\n%s\n    </ul>\n'
            '    <!-- journal:home:end -->\n'
            '  </section>\n\n' % (esc(jui_l["journal"]), lang, esc(d["journal_all"]), "\n".join(cards)))


def cluster():
    return [("x-default", home_url())] + [(l, home_url(l)) for l in LANGS]


def hreflang_block():
    return "<!-- hreflang: one static page per language (query-string free) -->\n" + "\n".join(
        '<link rel="alternate" hreflang="%s" href="%s">' % (h, u) for h, u in cluster())


def between(src, a, b):
    i = src.index(a)
    return src[i:src.index(b, i)]


def sub1(src, pat, repl, flags=0):
    new, n = re.subn(pat, lambda m: repl, src, count=1, flags=flags)
    if n != 1:
        raise SystemExit("home_sync: template marker not found: " + pat)
    return new


def ld_fix(src, lang, url):
    """WebSite: url + inLanguage of this page. FAQ (English text) only on the English page."""
    src = sub1(src, r'"@id": "https://ipe\.rest/#website",\n  "name": "ipe\(\)",\n  "url": "https://ipe\.rest/",\n  "inLanguage": \[[^\]]*\],',
               '"@id": "%s#website",\n  "name": "ipe()",\n  "url": "%s",\n  "inLanguage": "%s",' % (url, url, lang))
    if lang != "en":
        src = sub1(src, r'<script type="application/ld\+json" id="faq-jsonld">.*?</script>\n', "", re.S)
    return src


SCRIPT = """<script>
(function () {
  var LANG = '%(lang)s';
  var VALID = %(langs)s;
  // retired lang-query links -> the static page of that language
  try {
    var q = new URLSearchParams(location.search).get('lang');
    if (q && VALID.indexOf(q) !== -1 && q !== LANG) { location.replace('/' + q + '/' + location.hash); return; }
  } catch (e) {}
  var sel = document.getElementById('lang');
  if (sel) sel.addEventListener('change', function () {
    try { localStorage.setItem('ipe_lang', this.value); } catch (e) {}  // saved only on an explicit choice
    location.href = '/' + this.value + '/';
  });
  // mobile nav (<=760px): disclosure toggle, Esc / link click closes
  var head = document.querySelector('.site-head'), btn = document.getElementById('menu-btn');
  function setMenu(open) { if (!head || !btn) return; head.classList.toggle('is-open', open); btn.setAttribute('aria-expanded', open ? 'true' : 'false'); }
  if (btn) btn.addEventListener('click', function () { setMenu(btn.getAttribute('aria-expanded') !== 'true'); });
  document.addEventListener('keydown', function (e) { if (e.key === 'Escape' && head && head.classList.contains('is-open')) { setMenu(false); btn.focus(); } });
  var navLinks = document.querySelectorAll('#site-nav a');
  for (var k = 0; k < navLinks.length; k++) navLinks[k].addEventListener('click', function () { setMenu(false); });
})();
</script>"""


def render_lang(src, ui, lang, posts):
    d = dict(ui["en"])
    d.update(ui[lang])
    url = home_url(lang)
    out = src
    # visible strings: innerHTML of every [data-i18n] element
    def fill(m):
        key = m.group(3)
        if key not in d:
            raise SystemExit("home_sync: missing key %s (%s)" % (key, lang))
        return "<%s%s>%s</%s>" % (m.group(1), m.group(2), d[key], m.group(1))
    out = re.sub(r'<(\w+)([^>]*data-i18n="(\w+)"[^>]*)>(.*?)</\1>', fill, out, flags=re.S)
    out = sub1(out, r'<html lang="en" dir="ltr">', '<html lang="%s" dir="%s">' % (lang, "rtl" if lang in RTL else "ltr"))
    out = sub1(out, r'<title id="doc-title">.*?</title>', '<title>%s</title>' % html.escape(d["meta_title"], quote=False))
    out = sub1(out, r'<meta name="description" id="meta-desc" content="[^"]*">', '<meta name="description" content="%s">' % esc(d["meta_desc"]))
    out = sub1(out, r'<link rel="canonical" id="canonical" href="[^"]*">', '<link rel="canonical" href="%s">' % url)
    out = sub1(out, r'<!-- home:hreflang -->', hreflang_block())
    out = sub1(out, r'<meta property="og:title" id="og-title" content="[^"]*">', '<meta property="og:title" content="%s">' % esc(d["meta_title"]))
    out = sub1(out, r'<meta property="og:description" id="og-desc" content="[^"]*">', '<meta property="og:description" content="%s">' % esc(d["meta_desc"]))
    out = sub1(out, r'<meta property="og:url" id="og-url" content="[^"]*">', '<meta property="og:url" content="%s">' % url)
    alts = "\n".join('<meta property="og:locale:alternate" content="%s">' % OG_LOCALE[l] for l in LANGS if l != lang)
    out = sub1(out, r'<meta property="og:locale" id="og-locale" content="[^"]*">\n(?:<meta property="og:locale:alternate" content="[^"]*">\n?)+',
               '<meta property="og:locale" content="%s">\n%s\n' % (OG_LOCALE[lang], alts))
    out = sub1(out, r'<meta name="twitter:title" content="[^"]*">', '<meta name="twitter:title" content="%s">' % esc(d["meta_title"]))
    out = sub1(out, r'<meta name="twitter:description" content="[^"]*">', '<meta name="twitter:description" content="%s">' % esc(d["meta_desc"]))
    out = ld_fix(out, lang, url)
    out = out.replace('href="/journal/en/"', 'href="/journal/%s/"' % lang)
    if lang in J.TR_LANGS:  # machine-translated home: same notice as journal/about (EN is the source of truth)
        u = jui_ai[lang]
        note = ('<p class="ai-note" role="note" style="max-width:1200px;margin:16px auto 0;padding:12px 16px;width:calc(100%% - 32px);border:1px solid var(--line-soft);'
                'border-inline-start:2px solid var(--cobalt);background:var(--tint);color:var(--text);font:400 14px/1.7 var(--sans);box-sizing:border-box">'
                '<strong style="color:var(--ink);font-weight:600;margin-inline-end:4px">%s</strong> %s <a href="/en/" hreflang="en" style="color:var(--cobalt);text-decoration:underline">%s</a></p>\n'
                % (esc(u["ai_label"]), esc(u["ai_text"]), esc(u["ai_link"])))
        out = sub1(out, r'<main id="main">\n', '<main id="main">\n' + note)
    for pg in ("about", "contact", "privacy"):
        out = out.replace('href="/%s/"' % pg, 'href="/%s/%s/"' % (lang, pg))
    opts = "\n".join('        <option value="%s"%s>%s</option>' % (l, " selected" if l == lang else "", l.upper()) for l in LANGS)
    out = sub1(out, r'<!-- home:options -->', opts)
    out = sub1(out, r'<!-- home:journal -->\n', journal_section(posts, lang, jui_ai[lang], d))
    out = sub1(out, r'<!-- home:localtime -->', J.localtime_script() if "data-ipe-time" in out else "")
    out = sub1(out, r'<!-- home:script -->', SCRIPT % {"lang": lang, "langs": json.dumps(LANGS)})
    return out


CHOOSER_CSS = """:root{--bg:#fbfcfe;--ink:#0f1b33;--muted:#5b6784;--cobalt:#1f4fd8;--line:#d7deec}
@media (prefers-color-scheme:dark){:root:not([data-force]){--bg:#0d1424;--ink:#e8edf8;--muted:#9aa6c4;--cobalt:#8fb0ff;--line:#26314d}}
*{box-sizing:border-box}html{-webkit-text-size-adjust:100%}
body{margin:0;background:var(--bg);color:var(--ink);font:16px/1.6 Inter,system-ui,-apple-system,"Segoe UI",sans-serif}
.wrap{max-width:720px;margin:0 auto;padding:0 20px}
header{padding:24px 0;border-bottom:1px solid var(--line)}
.logo{font:600 20px "JetBrains Mono",ui-monospace,monospace;color:var(--cobalt);text-decoration:none}
.tagline{display:block;margin-top:4px;font:12px "JetBrains Mono",ui-monospace,monospace;color:var(--muted)}
h1{font-size:clamp(28px,6vw,40px);line-height:1.15;margin:40px 0 12px;font-weight:600}
p.lede{color:var(--muted);margin:0 0 28px}
#suggest{display:none;margin:0 0 20px;padding:12px 16px;border:1px solid var(--cobalt);color:var(--cobalt)}
#suggest a{color:inherit;font-weight:600}
ul{list-style:none;margin:0 0 48px;padding:0;display:grid;grid-template-columns:repeat(auto-fill,minmax(210px,1fr));gap:10px}
.lg{display:flex;flex-direction:column;justify-content:center;min-height:56px;padding:10px 16px;border:1px solid var(--line);color:var(--ink);text-decoration:none}
.lg:hover,.lg:focus-visible{border-color:var(--cobalt)}
.lg:focus-visible{outline:2px solid var(--cobalt);outline-offset:2px}
.lg-name{font-weight:600}.lg-sub{font:12px "JetBrains Mono",ui-monospace,monospace;color:var(--muted)}
footer{padding:24px 0 40px;border-top:1px solid var(--line);color:var(--muted);font:12px "JetBrains Mono",ui-monospace,monospace}
footer a{color:inherit}
@font-face{font-family:"Inter";font-weight:400;font-display:swap;src:url("/fonts/inter-400.woff2?v=23") format("woff2")}
@font-face{font-family:"JetBrains Mono";font-weight:400;font-display:swap;src:url("/fonts/jbmono-400.woff2?v=23") format("woff2")}"""


def render_chooser(src, ui):
    en = ui["en"]
    title = "ipe() — quiet things for busy minds · choose your language"
    desc = "Choose your language: " + en["meta_desc"]
    ga = between(src, "<!-- ===== Google Analytics", "<!-- ===== PWA")
    sw = between(src, "<!-- ===== PWA service worker", "<!-- home:localtime")
    org = between(src, '<script type="application/ld+json">\n{\n  "@context": "https://schema.org",\n  "@type": "Organization"', "</script>") + "</script>"
    site_ld = json.dumps({"@context": "https://schema.org", "@type": "WebSite", "@id": home_url() + "#website", "name": "ipe()",
                          "url": home_url(), "inLanguage": LANGS, "publisher": {"@id": home_url() + "#organization"}},
                         ensure_ascii=False, indent=2)
    items = "\n".join('    <li><a class="lg" lang="%s" hreflang="%s" href="/%s/"><span class="lg-name">%s</span>'
                      '<span class="lg-sub">ipe.rest/%s/</span></a></li>' % (l, l, l, NATIVE[l], l) for l in LANGS)
    names = json.dumps({l: NATIVE[l] for l in LANGS}, ensure_ascii=False)
    alts = "\n".join('<meta property="og:locale:alternate" content="%s">' % OG_LOCALE[l] for l in LANGS if l != "en")
    return """<!DOCTYPE html>
<html lang="en" dir="ltr" data-chooser>
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>%(title)s</title>
<meta name="description" content="%(desc)s">
<meta name="author" content="ipe()">
<meta name="robots" content="index, follow, max-image-preview:large, max-snippet:-1, max-video-preview:-1">
<meta name="theme-color" content="#fbfcfe">
<link rel="canonical" href="%(root)s">
<link rel="manifest" href="/manifest.webmanifest?v=23">
<link rel="icon" type="image/png" sizes="192x192" href="/icon-192.png?v=23">
<link rel="apple-touch-icon" href="/icon-180.png?v=23">
%(hreflang)s
<meta property="og:type" content="website">
<meta property="og:site_name" content="ipe()">
<meta property="og:title" content="%(title)s">
<meta property="og:description" content="%(desc)s">
<meta property="og:url" content="%(root)s">
<meta property="og:image" content="%(site)s/og-image.png">
<meta property="og:locale" content="en_US">
%(alts)s
<meta name="twitter:card" content="summary_large_image">
<meta name="twitter:title" content="%(title)s">
<meta name="twitter:description" content="%(desc)s">
<meta name="twitter:image" content="%(site)s/og-image.png">
%(org)s
<script type="application/ld+json">
%(site_ld)s
</script>
<style>
%(css)s
</style>
</head>
<body>
<header><div class="wrap"><a class="logo" href="/" aria-label="ipe() home">ipe()</a><span class="tagline">when the process finally rests</span></div></header>
<main class="wrap">
  <h1>Choose your language</h1>
  <p class="lede">ipe() — quiet things for busy minds. A small AI-native studio in Seoul. The home page is available in 12 languages.</p>
  <p id="suggest" role="status"></p>
  <ul aria-label="Languages">
%(items)s
  </ul>
</main>
<footer><div class="wrap">ipe() · idle &nbsp;·&nbsp; AI draft + human review &nbsp;·&nbsp; <a href="/journal/">journal</a> · <a href="/about/">about</a> · <a href="/contact/">contact</a> · <a href="/privacy/">privacy</a></div></footer>

%(ga)s
%(sw)s
<script>
(function () {
  var VALID = %(langs)s, NAMES = %(names)s;
  var h = location.hash || '';
  try {  // retired lang-query links -> /xx/
    var q = new URLSearchParams(location.search).get('lang');
    if (q && VALID.indexOf(q) !== -1) { location.replace('/' + q + '/' + h); return; }
  } catch (e) {}
  var stored = null;
  try { stored = localStorage.getItem('ipe_lang'); } catch (e) {}
  // an explicit earlier choice is honoured; otherwise only suggest the browser language (no automatic redirect)
  if (stored && VALID.indexOf(stored) !== -1) { location.replace('/' + stored + '/' + h); return; }
  try {
    var list = navigator.languages || [navigator.language];
    for (var i = 0; i < list.length; i++) {
      var c = (list[i] || '').toLowerCase().split('-')[0];
      if (VALID.indexOf(c) !== -1) {
        var box = document.getElementById('suggest');
        box.innerHTML = '';
        var a = document.createElement('a');
        a.href = '/' + c + '/'; a.textContent = NAMES[c] + ' →'; a.lang = c;
        box.appendChild(a); box.style.display = 'block';
        a.addEventListener('click', function () { try { localStorage.setItem('ipe_lang', c); } catch (e) {} });
        break;
      }
    }
  } catch (e) {}
  var links = document.querySelectorAll('.lg');
  for (var k = 0; k < links.length; k++) links[k].addEventListener('click', function () {
    try { localStorage.setItem('ipe_lang', this.getAttribute('hreflang')); } catch (e) {}
  });
})();
</script>
</body>
</html>
""" % {"title": esc(title), "desc": esc(desc), "root": home_url(), "site": SITE, "hreflang": hreflang_block(), "alts": alts,
       "org": org, "site_ld": site_ld, "css": CHOOSER_CSS, "items": items, "ga": ga.strip(), "sw": sw.strip(),
       "langs": json.dumps(LANGS), "names": names}


def sitemap_block(lastmod=LASTMOD):
    out = ["  <!-- home:start -->"]
    for lang in [None] + LANGS:
        pr = "1.0" if lang in (None, "en") else "0.9"
        out += ["  <url>", "    <loc>%s</loc>" % home_url(lang), "    <lastmod>%s</lastmod>" % lastmod,
                "    <changefreq>weekly</changefreq>", "    <priority>%s</priority>" % pr]
        out += ['    <xhtml:link rel="alternate" hreflang="%s" href="%s"/>' % (h, u) for h, u in cluster()]
        out += ["    <image:image><image:loc>%s/og-image.png</image:loc></image:image>" % SITE, "  </url>"]
    out.append("  <!-- home:end -->")
    return "\n".join(out)


def llms_block():
    lines = ["<!-- home:llms:start -->",
             "- Main page (12 languages, one static page per language; root is a language chooser): %s" % home_url()]
    lines += ["  - %s [%s]: %s" % (NATIVE[l], l, home_url(l)) for l in LANGS]
    lines.append("<!-- home:llms:end -->")
    return "\n".join(lines)


class _Bal(HTMLParser):
    VOID = {"meta", "link", "br", "img", "input", "path", "circle", "rect", "line", "hr", "source", "stop"}

    def __init__(self):
        super().__init__()
        self.stack, self.err = [], []

    def handle_starttag(self, tag, attrs):
        if tag not in self.VOID:
            self.stack.append(tag)

    def handle_startendtag(self, tag, attrs):
        pass

    def handle_endtag(self, tag):
        if tag in self.VOID:
            return
        if not self.stack or self.stack[-1] != tag:
            self.err.append("unbalanced </%s>" % tag)
        else:
            self.stack.pop()


def balanced(text):
    p = _Bal()
    p.feed(text)
    return p.err + (["unclosed " + ",".join(p.stack)] if p.stack else [])


def replace_between(text, start, end, block):
    i = text.index(start)
    j = text.index(end) + len(end)
    return text[:i] + block + text[j:]


def build(root=ROOT):
    src, ui = load(root)
    posts = journal_posts(root)
    writes, errors = {}, []
    for l in LANGS:
        writes[root / l / "index.html"] = render_lang(src, ui, l, posts)
    writes[root / "index.html"] = render_chooser(src, ui)
    for p, t in writes.items():
        errors += ["%s: %s" % (p.relative_to(root), e) for e in balanced(t)]
    sm = (root / "sitemap.xml").read_text(encoding="utf-8")
    if "<!-- home:start -->" not in sm:  # first run: swap the old hand-written root <url> for the generated block
        sm = sub1(sm, r'  <url>\n    <loc>https://ipe\.rest/</loc>.*?</url>\n(?=  <!-- journal:start -->)', "  <!-- home:start -->\n  <!-- home:end -->\n", re.S)
    writes[root / "sitemap.xml"] = replace_between(sm, "  <!-- home:start -->", "<!-- home:end -->", sitemap_block(max([p['published'] for p, _d in posts] + [LASTMOD])))
    lt = (root / "llms.txt").read_text(encoding="utf-8")
    if "<!-- home:llms:start -->" not in lt:
        lt = lt.replace("## Journal\n", "## Main page\n<!-- home:llms:start -->\n<!-- home:llms:end -->\n\n## Journal\n", 1)
    writes[root / "llms.txt"] = replace_between(lt, "<!-- home:llms:start -->", "<!-- home:llms:end -->", llms_block())
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
        print("wrote", p.relative_to(ROOT))
    return 0


if __name__ == "__main__":
    sys.exit(main())
