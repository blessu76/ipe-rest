#!/usr/bin/env python3
"""Keep the ipe.rest journal's index data in sync with the posts — stdlib only (Python 3.8+).

Posts are hand-written HTML (journal/<YYYY-MM-DD-slug>/index.html, EN+KO in one file; start from
scripts/journal-post-template.html). This script READS every post and rewrites only generated blocks:

    journal/index.html   <!-- journal:list:start/end -->  post cards
                         <!-- journal:ld:start/end -->    Blog + ItemList JSON-LD
    sitemap.xml          <!-- journal:start/end -->        /journal/ + every post (lastmod, hreflang, image:image)
    llms.txt             <!-- journal:llms:start/end -->   post list
    each post            "wordCount" in its BlogPosting JSON-LD (words of the EN prose)

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

ROOT = Path(__file__).resolve().parent.parent
SITE = "https://ipe.rest"
ORG_ID = SITE + "/#organization"
DIR_RE = re.compile(r"^(\d{4}-\d{2}-\d{2})-[a-z0-9]+(?:-[a-z0-9]+)*$")
IMG_NS = "http://www.google.com/schemas/sitemap-image/1.1"
LD_RE = re.compile(r'<script type="application/ld\+json">\s*(.*?)\s*</script>', re.S)
WORDCOUNT_RE = re.compile(r'("wordCount":\s*)\d+')
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


def check_placeholders(d, src, ld):
    """Errors for template leftovers (TODO, YYYY-MM-DD, folder slug 'slug', unclosed <h2>)."""
    errs = []
    if re.sub(r"^\d{4}-\d{2}-\d{2}-", "", d.name) == "slug":
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


def load_post(d, root=ROOT):
    """Parse + validate one post dir. Returns (post dict, [errors])."""
    path = d / "index.html"
    src = path.read_text(encoding="utf-8")
    errs = []
    url = "%s/journal/%s/" % (SITE, d.name)
    post = {"dir": d, "path": path, "src": src, "slug": d.name, "url": url}

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
    for lang in ("en", "ko", "x-default"):
        want = url if lang == "x-default" else "%s?lang=%s" % (url, lang)
        if '<link rel="alternate" hreflang="%s" href="%s">' % (lang, want) not in src:
            errs.append("missing hreflang=%s alternate (%s)" % (lang, want))
    if "<article" not in src:
        errs.append("missing <article>")
    if len(re.findall(r"<h1[ >]", src)) != 2:
        errs.append("need exactly two <h1> (lang=en, lang=ko)")
    if len(re.findall(r"<h2[ >]", src)) < 1 and prose_words(src, "en") > 400:
        errs.append("long post without any <h2>")

    for key in ("headline", "alternativeHeadline", "description", "datePublished", "dateModified"):
        if not ld.get(key):
            errs.append("BlogPosting.%s is empty" % key)
    for key in ("image", "keywords", "about", "inLanguage"):
        if not ld.get(key):
            errs.append("BlogPosting.%s is empty" % key)
    if "wordCount" not in ld:
        errs.append("BlogPosting.wordCount missing (any number; the script fills it in)")
    errs += check_placeholders(d, src, ld)
    errs += check_images(root, src, ld)
    author = ld.get("author")
    if not isinstance(author, dict) or author.get("@type") != "Organization":
        errs.append("author must be an Organization (no personal names)")
    if "@" in json.dumps(ld, ensure_ascii=False).replace("@type", "").replace("@id", "").replace("@context", ""):
        errs.append("JSON-LD contains '@' — e-mail addresses do not belong in posts' structured data")
    if ld.get("url") != url:
        errs.append("BlogPosting.url must be %s" % url)
    if not d.name.startswith(str(ld.get("datePublished", ""))):
        errs.append("folder date must equal datePublished")

    ex_en, ex_ko = meta(src, "ipe:excerpt-en"), meta(src, "ipe:excerpt-ko")
    if not ex_en or not ex_ko:
        errs.append("missing <meta name=ipe:excerpt-en / ipe:excerpt-ko>")
    post.update(
        ld=ld,
        title_en=ld.get("headline", ""),
        title_ko=ld.get("alternativeHeadline", ""),
        desc=meta(src, "description") or ld.get("description", ""),
        excerpt_en=ex_en or "",
        excerpt_ko=ex_ko or "",
        category=meta(src, "ipe:category") or "studio",
        published=ld.get("datePublished", ""),
        modified=ld.get("dateModified", ld.get("datePublished", "")),
        words=prose_words(src, "en"),
    )
    img = ld.get("image")
    post["image"] = img if isinstance(img, dict) else {"url": img}
    return post, errs


def j(obj, indent):
    """JSON pretty-printed, continuation lines indented."""
    s = json.dumps(obj, ensure_ascii=False, indent=2)
    return s.replace("\n", "\n" + indent)


def render_list(posts):
    items = []
    for p in posts:
        items.append(f'''    <li>
      <a class="post-card" href="/journal/{p['slug']}/">
        <p class="post-meta"><time datetime="{p['published']}">{p['published']}</time> · {html.escape(p['category'])}</p>
        <h2 lang="en">{html.escape(p['title_en'], quote=False)}</h2>
        <h2 lang="ko">{html.escape(p['title_ko'], quote=False)}</h2>
        <p class="excerpt" lang="en">{html.escape(p['excerpt_en'], quote=False)}</p>
        <p class="excerpt" lang="ko">{html.escape(p['excerpt_ko'], quote=False)}</p>
        <span class="more"><span lang="en">read →</span><span lang="ko">읽기 →</span></span>
      </a>
    </li>''')
    return "\n".join(items)


def render_ld(posts):
    entries = []
    for p in posts:
        e = {"@type": "BlogPosting", "@id": p["url"] + "#article", "headline": p["title_en"], "alternativeHeadline": p["title_ko"],
             "description": p["desc"], "url": p["url"], "datePublished": p["published"],
             "dateModified": p["modified"], "inLanguage": ["en", "ko"]}
        if p["image"].get("url"):
            e["image"] = p["image"]["url"]
        entries.append(e)
    graph = [
        {"@type": "Blog", "@id": SITE + "/journal/#blog", "name": "ipe() journal", "url": SITE + "/journal/",
         "description": "Notes from ipe(), a small AI-native studio in Seoul making quiet, developer-minded things.",
         "inLanguage": ["en", "ko"],
         "publisher": {"@type": "Organization", "@id": ORG_ID, "name": "ipe()", "url": SITE + "/"},
         "blogPost": entries},
        {"@type": "ItemList", "@id": SITE + "/journal/#list", "name": "ipe() journal — all posts",
         "itemListOrder": "https://schema.org/ItemListOrderDescending", "numberOfItems": len(posts),
         "itemListElement": [{"@type": "ListItem", "position": i + 1, "url": p["url"], "name": p["title_en"]}
                             for i, p in enumerate(posts)]},
    ]
    doc = {"@context": "https://schema.org", "@graph": graph}
    return '<script type="application/ld+json">\n%s\n</script>' % json.dumps(doc, ensure_ascii=False, indent=2)


def render_sitemap(posts):
    newest = max(p["modified"] for p in posts)
    out = ["""  <url>
    <loc>%s/journal/</loc>
    <lastmod>%s</lastmod>
    <changefreq>weekly</changefreq>
    <priority>0.8</priority>
  </url>""" % (SITE, newest)]
    for p in posts:
        u = p["url"]
        img = ""
        if p["image"].get("url"):
            img = "\n    <image:image><image:loc>%s</image:loc></image:image>" % html.escape(p["image"]["url"])
        out.append(f"""  <url>
    <loc>{u}</loc>
    <lastmod>{p['modified']}</lastmod>
    <changefreq>monthly</changefreq>
    <priority>0.6</priority>
    <xhtml:link rel="alternate" hreflang="x-default" href="{u}"/>
    <xhtml:link rel="alternate" hreflang="en" href="{u}?lang=en"/>
    <xhtml:link rel="alternate" hreflang="ko" href="{u}?lang=ko"/>{img}
  </url>""")
    return "\n".join(out)


def render_llms(posts):
    lines = ["- Journal (EN/KO, weekly): %s/journal/" % SITE]
    for p in posts:
        lines.append("- %s (%s): %s - %s" % (p["title_en"], p["published"], p["url"], p["desc"]))
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


def build(root=ROOT):
    """Returns ({path: new_text}, [errors]) without writing."""
    jdir = root / "journal"
    dirs = sorted((d for d in jdir.iterdir() if d.is_dir() and DIR_RE.match(d.name) and (d / "index.html").exists()),
                  key=lambda d: d.name, reverse=True)
    posts, errors, writes = [], [], {}
    for d in dirs:
        p, errs = load_post(d, root)
        errors += ["%s: %s" % (d.name, e) for e in errs]
        if "ld" not in p:
            continue
        want = WORDCOUNT_RE.sub(lambda m: m.group(1) + str(p["words"]), p["src"], count=1)
        if want != p["src"]:
            writes[p["path"]] = want
        posts.append(p)
    if not posts:
        return writes, errors + ["no posts found"]

    idx = jdir / "index.html"
    t = idx.read_text(encoding="utf-8")
    t = replace_block(t, "<!-- journal:list:start -->", "<!-- journal:list:end -->", render_list(posts), "journal/index.html")
    t = replace_block(t, "<!-- journal:ld:start -->", "<!-- journal:ld:end -->", render_ld(posts), "journal/index.html")
    writes[idx] = t

    sm = root / "sitemap.xml"
    t = ensure_ns(sm.read_text(encoding="utf-8"))
    writes[sm] = replace_block(t, "<!-- journal:start -->", "<!-- journal:end -->", render_sitemap(posts), "sitemap.xml")

    ll = root / "llms.txt"
    t = ll.read_text(encoding="utf-8")
    writes[ll] = replace_block(t, "<!-- journal:llms:start -->", "<!-- journal:llms:end -->", render_llms(posts), "llms.txt")

    # generated output must still parse
    import xml.etree.ElementTree as ET
    try:
        ET.fromstring(writes[sm])
    except ET.ParseError as e:
        errors.append("sitemap.xml does not parse: %s" % e)
    for raw in LD_RE.findall(writes[idx]):
        try:
            json.loads(raw)
        except ValueError as e:
            errors.append("journal/index.html JSON-LD invalid: %s" % e)
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
    stale = [p for p, new in writes.items() if p.read_text(encoding="utf-8") != new]
    if a.check:
        for p in stale:
            print("out of date: %s" % p.relative_to(root), file=sys.stderr)
        print("journal_sync --check: %s" % ("OUT OF DATE — run scripts/journal_sync.py" if stale else "ok"))
        return 1 if stale else 0
    for p in stale:
        p.write_text(writes[p], encoding="utf-8")
        print("updated %s" % p.relative_to(root))
    print("journal_sync: %d file(s) updated" % len(stale) if stale else "journal_sync: already up to date")
    return 0


if __name__ == "__main__":
    sys.exit(main())
