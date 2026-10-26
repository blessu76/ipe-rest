#!/usr/bin/env python3
"""Generate the ipe.rest journal from post sources — stdlib only (Python 3.8+).

Posts are hand-written bilingual sources (scripts/journal_src/<YYYY-MM-DD-slug>.html, EN+KO; start from
scripts/journal-post-template.html). Not served. 10 more languages come from scripts/journal_i18n/<slug>/<lang>.json.
This script READS them and WRITES (see journal_i18n.py for the URL rules):

    journal/<lang>/<slug>/index.html   12 languages, single-language static pages (en/ko from the source)
    journal/<lang>/index.html          12 language lists (Blog + ItemList)
    journal/<slug>/index.html, journal/index.html   x-default language choosers
    sitemap.xml  <!-- journal:start/end -->        every page above, lastmod + 13 hreflang + image
    llms.txt     <!-- journal:llms:start/end -->   lists + posts per language

Usage:
    python3 scripts/journal_sync.py           # validate + rewrite
    python3 scripts/journal_sync.py --check   # validate only; exit 1 if anything is invalid or out of date
"""
import argparse
import datetime
import html
import json
import re
import sys
import urllib.parse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import journal_i18n as I18N  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
SITE = I18N.SITE
ORG_ID = I18N.ORG_ID
DIR_RE = re.compile(r"^(\d{4}-\d{2}-\d{2})-[a-z0-9]+(?:-[a-z0-9]+)*$")
IMG_NS = "http://www.google.com/schemas/sitemap-image/1.1"
LD_RE = re.compile(r'<script type="application/ld\+json">\s*(.*?)\s*</script>', re.S)
COMMENT_RE = re.compile(r"<!--.*?-->", re.S)
# leftovers from scripts/journal-post-template.html (folder slug "slug" is checked separately)
PLACEHOLDER_RE = re.compile(r"\bTODO\b|YYYY-MM-DD")


def meta(src, name, attr="name"):
    m = re.search(r'<meta %s="%s" content="([^"]*)"' % (attr, re.escape(name)), src)
    return html.unescape(m.group(1)) if m else None


def prose_words(src, lang):
    m = re.search(r'<div class="prose" lang="%s">(.*?)</div>' % lang, src, re.S)
    if not m:
        return 0
    return len(html.unescape(re.sub(r"<[^>]+>", " ", m.group(1))).split())


def local_file(root, url):
    """Map a site URL (https://ipe.rest/x/y.png) or root-relative path to a path under root.
    Returns None for other domains (not ours to check) and for paths that escape root."""
    if url.startswith(SITE + "/"):
        url = url[len(SITE):]
    if not url.startswith("/") or url.startswith("//"):
        return None
    f = (root / urllib.parse.unquote(re.split(r"[?#]", url, 1)[0]).lstrip("/")).resolve()
    return f if root.resolve() in f.parents else None


def check_images(root, src, ld):
    """Errors for image URLs (JSON-LD image/thumbnailUrl, og:image, twitter:image) that are not real files."""
    img = ld.get("image")
    urls = {"BlogPosting.image.url": img.get("url") if isinstance(img, dict) else img,
            "BlogPosting.thumbnailUrl": ld.get("thumbnailUrl"),
            "og:image": meta(src, "og:image", "property"),
            "twitter:image": meta(src, "twitter:image")}
    errs = []
    for label, u in urls.items():
        if not u or not isinstance(u, str):
            continue
        if not u.startswith(SITE + "/"):
            if u.startswith("/") or u.startswith(SITE):
                errs.append("%s must be an absolute %s/… URL: %s" % (label, SITE, u))
            continue  # other domains: not ours to check
        f = local_file(root, u)
        if f is None or not f.is_file():
            errs.append("%s points at a file that is not in the repo: %s" % (label, u))
    return errs


def check_placeholders(slug, src, ld):
    """Errors for template leftovers (TODO, YYYY-MM-DD, folder slug 'slug', unclosed <h2>)."""
    errs = []
    if re.sub(r"^\d{4}-\d{2}-\d{2}-", "", slug) == "slug":
        errs.append("folder name still uses the template slug 'slug'")
    body = COMMENT_RE.sub("", src)
    hits = sorted(set(PLACEHOLDER_RE.findall(body)))
    if hits:
        first = next(i for i, ln in enumerate(body.splitlines(), 1) if PLACEHOLDER_RE.search(ln))
        errs.append("template placeholder(s) left in the post: %s (first near line %d of the comment-stripped source) — "
                    "replace every TODO / YYYY-MM-DD" % (", ".join(hits), first))
    for key in ("datePublished", "dateModified"):
        v = ld.get(key)
        try:
            ok = isinstance(v, str) and re.fullmatch(r"\d{4}-\d{2}-\d{2}", v) and datetime.date.fromisoformat(v)
        except ValueError:
            ok = False
        if v and not ok:
            errs.append("BlogPosting.%s must be a real YYYY-MM-DD date (got %r)" % (key, v))
    if len(re.findall(r"<h2[ >]", body)) != len(re.findall(r"</h2>", body)):
        errs.append("unbalanced <h2> / </h2> (escape literal tags as &lt;h2&gt;)")
    return errs


def block(src, tag_re):
    m = re.search(tag_re, src, re.S)
    return m.group(1).strip() if m else ""


def load_post(path, root=ROOT):
    """Parse + validate one post source (scripts/journal_src/<slug>.html). Returns (post dict, [errors])."""
    path = Path(path)
    slug = path.stem
    src = path.read_text(encoding="utf-8")
    errs = []
    url = "%s/journal/%s/" % (SITE, slug)
    post = {"path": path, "src": src, "slug": slug, "url": url}

    ld = None
    for raw in LD_RE.findall(src):
        try:
            obj = json.loads(raw)
        except ValueError as e:
            errs.append("invalid JSON-LD: %s" % e)
            continue
        if obj.get("@type") == "BlogPosting":
            ld = obj
    if ld is None:
        errs.append("no BlogPosting JSON-LD")
        return post, errs

    canon = re.search(r'<link rel="canonical" href="([^"]+)"', src)
    if not canon or canon.group(1) != url:
        errs.append("canonical must be %s" % url)
    if "<article" not in src:
        errs.append("missing <article>")
    if len(re.findall(r"<h1[ >]", src)) != 2:
        errs.append("need exactly two <h1> (lang=en, lang=ko)")
    if len(re.findall(r"<h2[ >]", src)) < 1 and prose_words(src, "en") > 400:
        errs.append("long post without any <h2>")

    for key in ("headline", "alternativeHeadline", "description", "datePublished", "dateModified"):
        if not ld.get(key):
            errs.append("BlogPosting.%s is empty" % key)
    for key in ("image", "keywords", "about", "abstract"):
        if not ld.get(key):
            errs.append("BlogPosting.%s is empty" % key)
    errs += check_placeholders(slug, src, ld)
    errs += check_images(root, src, ld)
    author = ld.get("author")
    if not isinstance(author, dict) or author.get("@type") != "Organization":
        errs.append("author must be an Organization (no personal names)")
    if "@" in json.dumps(ld, ensure_ascii=False).replace("@type", "").replace("@id", "").replace("@context", ""):
        errs.append("JSON-LD contains '@' — e-mail addresses do not belong in posts' structured data")
    if ld.get("url") != url:
        errs.append("BlogPosting.url must be %s" % url)
    if not slug.startswith(str(ld.get("datePublished", ""))):
        errs.append("file name date must equal datePublished")

    ex_en, ex_ko = meta(src, "ipe:excerpt-en"), meta(src, "ipe:excerpt-ko")
    if not ex_en or not ex_ko:
        errs.append("missing <meta name=ipe:excerpt-en / ipe:excerpt-ko>")
    original = meta(src, "ipe:original")
    if original not in I18N.ORIG_LANGS:
        errs.append("missing <meta name=ipe:original content=en|ko> (the language the post was written in)")
        original = "en"
    langdata = {}
    for lang in I18N.ORIG_LANGS:
        d = {"title": ld.get("headline", "") if lang == "en" else ld.get("alternativeHeadline", ""),
             "description": (meta(src, "description") or ld.get("description", "")) if lang == "en" else (meta(src, "ipe:description-ko") or ""),
             "abstract": ld.get("abstract", "") if lang == "en" else (meta(src, "ipe:abstract-ko") or ""),
             "excerpt": (ex_en if lang == "en" else ex_ko) or "",
             "h1_html": block(src, r'<h1 lang="%s">(.*?)</h1>' % lang),
             "body": block(src, r'<div class="prose" lang="%s">(.*?)</div>' % lang)}
        if lang == "ko":
            for k, name in (("description", "ipe:description-ko"), ("abstract", "ipe:abstract-ko")):
                if not d[k]:
                    errs.append("missing <meta name=%s>" % name)
        errs += ["%s (%s)" % (e, lang) for e in I18N.check_post_data("source", d)]
        langdata[lang] = d
    post["langdata"] = langdata
    post["original"] = original
    pub_at = meta(src, "ipe:published-at") or ""
    if pub_at and not (re.fullmatch(r"\d{4}-\d{2}-\d{2}T([01]\d|2[0-3]):[0-5]\d\+09:00", pub_at)
                       and pub_at[:10] == ld.get("datePublished")):
        errs.append("ipe:published-at must be YYYY-MM-DDTHH:MM+09:00 (KST, no seconds) on the datePublished date (got %r)" % pub_at)
        pub_at = ""
    post["published_at"] = pub_at
    post.update(
        ld=ld,
        category=meta(src, "ipe:category") or "studio",
        published=ld.get("datePublished", ""),
        modified=ld.get("dateModified", ld.get("datePublished", "")),
    )
    img = ld.get("image")
    post["image"] = img if isinstance(img, dict) else {"url": img}
    return post, errs


def _xlinks(cluster):
    return "\n".join('    <xhtml:link rel="alternate" hreflang="%s" href="%s"/>' % (h, html.escape(u)) for h, u in cluster)


def render_sitemap(posts, tr):
    """tr = {slug: {lang: data}} — every language page (and the x-default chooser) gets its own <url> with the full hreflang cluster."""
    list_langs = {l for v in tr.values() for l in v}
    newest = max(p["modified"] for p in posts)
    lcl = _xlinks(I18N.list_cluster(list_langs))
    out = []
    for loc in [I18N.list_url()] + [I18N.list_url(l) for l in I18N.LANGS if l in list_langs]:
        out.append("""  <url>
    <loc>%s</loc>
    <lastmod>%s</lastmod>
    <changefreq>weekly</changefreq>
    <priority>%s</priority>
%s
  </url>""" % (loc, newest, "0.8" if loc == I18N.list_url() or loc == I18N.list_url("en") else "0.7", lcl))
    for p in posts:
        langs = set(tr[p["slug"]])
        cl = _xlinks(I18N.post_cluster(p["slug"], langs))
        img = ""
        if p["image"].get("url"):
            img = "\n    <image:image><image:loc>%s</image:loc></image:image>" % html.escape(p["image"]["url"])
        for h, loc in I18N.post_cluster(p["slug"], langs):
            lm = (tr[p["slug"]].get(h, {}).get("dateModified") if h != "x-default" else None) or p["modified"]
            out.append(f"""  <url>
    <loc>{loc}</loc>
    <lastmod>{lm}</lastmod>
    <changefreq>monthly</changefreq>
    <priority>{"0.6" if h in ("x-default", p["original"]) else "0.5"}</priority>
{cl}{img}
  </url>""")
    return "\n".join(out)


def render_llms(posts, tr):
    list_langs = {l for v in tr.values() for l in v}
    lines = ["- Journal (12 languages, one static page per language; language chooser): %s/journal/" % SITE]
    for l in I18N.LANGS:
        if l in list_langs:
            lines.append("  - %s [%s]%s: %s" % (I18N.NATIVE[l], l, " (AI translation)" if l in I18N.TR_LANGS else "", I18N.list_url(l)))
    for p in posts:
        en = tr[p["slug"]]["en"]
        lines.append("- %s (%s): %s - %s" % (en["title"], p["published"], p["url"], en["description"]))
        lines.append("  - original language: %s" % p["original"])
        for l in I18N.LANGS:
            if l in tr[p["slug"]]:
                lines.append("  - [%s] %s%s: %s" % (l, tr[p["slug"]][l]["title"], " (AI translation)" if l in I18N.TR_LANGS else "", I18N.post_url(p["slug"], l)))
    return "\n".join(lines)


def replace_block(text, start, end, body, name):
    pat = re.compile(r"(%s).*?\n?([ \t]*)(%s)" % (re.escape(start), re.escape(end)), re.S)
    if not pat.search(text):
        raise SystemExit("%s: markers %s … %s not found" % (name, start, end))
    return pat.sub(lambda m: "%s\n%s\n%s%s" % (m.group(1), body, m.group(2), m.group(3)), text, count=1)


def ensure_ns(text):
    if "xmlns:image=" not in text:
        text = text.replace('<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"',
                            '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"\n        xmlns:image="%s"' % IMG_NS, 1)
    return text


def slug_of(url):
    return url.rstrip("/").rsplit("/", 1)[-1]


def build(root=ROOT):
    """Returns ({path: new_text}, [errors]) without writing."""
    jdir = root / "journal"
    sdir = root / "scripts" / "journal_src"
    files = sorted((f for f in sdir.glob("*.html") if DIR_RE.match(f.stem)), key=lambda f: f.stem, reverse=True) if sdir.is_dir() else []
    ui, tr, i18n_errs = I18N.load(root)
    posts, errors, writes = [], list(i18n_errs), {}
    for f in files:
        p, errs = load_post(f, root)
        errors += ["%s: %s" % (f.stem, e) for e in errs]
        if "ld" not in p or "langdata" not in p:
            continue
        posts.append(p)
    if not posts:
        return writes, errors + ["no posts found"]
    slugs = {p["slug"] for p in posts}
    for slug in tr:
        if slug not in slugs:
            errors.append("journal_i18n/%s has no matching post source in scripts/journal_src/" % slug)
    # every post: 12 languages = en/ko from the source + translations
    allp = {}
    for p in posts:
        allp[p["slug"]] = dict(p["langdata"])
        allp[p["slug"]].update(tr.get(p["slug"], {}))
    used = {l for v in allp.values() for l in v}
    ui_errs, bad = I18N.ui_errors(ui, used)
    errors += ui_errs
    allp = {s: {l: d for l, d in v.items() if l not in bad} for s, v in allp.items()}
    list_langs = {l for v in allp.values() for l in v}
    if bad or not ({"en", "ko"} <= list_langs):
        return writes, errors + ([] if not ({"en", "ko"} - list_langs) else ["en and ko pages could not be generated"])

    for p in posts:
        slug = p["slug"]
        langs = set(allp[slug])
        for l in I18N.LANGS:
            if l in langs:
                writes[jdir / l / slug / "index.html"] = I18N.render_post(p, l, ui, allp[slug][l], langs)
        writes[jdir / slug / "index.html"] = I18N.render_chooser_post(p, ui, allp[slug], langs)
    for l in I18N.LANGS:
        if l in list_langs:
            items = [(p, allp[p["slug"]][l]) for p in posts if l in allp[p["slug"]]]
            writes[jdir / l / "index.html"] = I18N.render_list_page(l, ui, items, list_langs)
    writes[jdir / "index.html"] = I18N.render_chooser_list(ui, allp, list_langs, posts=posts)

    # orphans: generated pages whose source is gone (posts removed or language dropped)
    for l in I18N.LANGS:
        for f in (jdir / l).glob("*/index.html") if (jdir / l).is_dir() else []:
            if f not in writes:
                errors.append("orphan generated page %s (no source) — delete it" % f.relative_to(root))
    for f in jdir.glob("*/index.html"):
        if DIR_RE.match(f.parent.name) and f not in writes:
            errors.append("orphan generated page %s (no source) — delete it" % f.relative_to(root))

    sm = root / "sitemap.xml"
    t = ensure_ns(sm.read_text(encoding="utf-8"))
    writes[sm] = replace_block(t, "<!-- journal:start -->", "<!-- journal:end -->", render_sitemap(posts, allp), "sitemap.xml")

    ll = root / "llms.txt"
    t = ll.read_text(encoding="utf-8")
    writes[ll] = replace_block(t, "<!-- journal:llms:start -->", "<!-- journal:llms:end -->", render_llms(posts, allp), "llms.txt")

    # generated output must still parse
    import xml.etree.ElementTree as ET
    try:
        ET.fromstring(writes[sm])
    except ET.ParseError as e:
        errors.append("sitemap.xml does not parse: %s" % e)
    for path, text in writes.items():
        if path.suffix == ".html":
            for raw in LD_RE.findall(text):
                try:
                    json.loads(raw)
                except ValueError as e:
                    errors.append("%s JSON-LD invalid: %s" % (path.relative_to(root), e))
    return writes, errors


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--check", action="store_true", help="validate only, write nothing")
    ap.add_argument("--root", default=str(ROOT), help="site root (default: repo root)")
    a = ap.parse_args(argv)
    root = Path(a.root)
    writes, errors = build(root)
    if errors:
        print("journal_sync: %d problem(s):" % len(errors), file=sys.stderr)
        for e in errors:
            print("  - " + e, file=sys.stderr)
        return 1
    stale = [p for p, new in writes.items() if not p.exists() or p.read_text(encoding="utf-8") != new]
    if a.check:
        for p in stale:
            print("out of date: %s" % p.relative_to(root), file=sys.stderr)
        print("journal_sync --check: %s" % ("OUT OF DATE — run scripts/journal_sync.py" if stale else "ok"))
        return 1 if stale else 0
    for p in stale:
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(writes[p], encoding="utf-8")
        print("updated %s" % p.relative_to(root))
    print("journal_sync: %d file(s) updated" % len(stale) if stale else "journal_sync: already up to date")
    return 0


if __name__ == "__main__":
    sys.exit(main())
