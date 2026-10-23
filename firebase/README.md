# firebase/ — ipe web (like + comment widget backend)

Not deployed with the site (excluded by `scripts/build_site.sh`). Spark (free) plan only — **never attach a billing account**: past the free quota requests simply fail and the widget hides itself.

- `firestore.rules` — the defence line. Comments: create only, name 1–30 / text 1–500 chars, no links (`http`, `www.`, `://`), `createdAt == request.time`. Likes: one doc per post, `count` +1 only. Everything else denied.
- Project: id in `.firebaserc` (default alias), Firestore location `asia-northeast3` (Seoul). Web config (project id + web API key) lives in one place: `DEFAULTS` at the top of `widget/ipe-engage.js`. The web key is public by design; restrict it to HTTP referrers `https://ipe.rest/*` (and other sites you add) in Google Cloud Console → APIs & Services → Credentials.
- Deploy rules: `cd firebase && firebase deploy --only firestore:rules`.
- **Delete a comment (admin)**: Firebase console → Firestore → `posts/<site>__<slug>/comments/<id>` → delete; or CLI `firebase firestore:delete posts/<site>__<slug>/comments/<id> --project <id>`. Resetting a like count: edit `count` on `posts/<site>__<slug>` in the console.
- Rules tests: `firebase emulators:exec` needs Java (not installed here) — verified by hand against the live project instead (see the PR notes).

## Add the widget to another site (3 lines)
1. Allow the site in `validPid()` in `firestore.rules` (and the key's referrer list), then redeploy rules.
2. In the page, under the article:
```html
<link rel="stylesheet" href="https://ipe.rest/widget/ipe-engage.css?v=1">
<section class="ipe-engage" data-site="idle.ipe.rest" data-post="<post-slug>" data-lang="en"></section>
<script src="https://ipe.rest/widget/ipe-engage.js?v=1" defer></script>
```
`data-post` = lowercase letters/digits/hyphens (3–100). `data-lang` = one of en ko ja zh es fr de pt ru ar hi id. `data-theme="auto"` follows the visitor's dark mode (default: light).
