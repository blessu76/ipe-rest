# Changelog

## 2026-11-12

### Web kit v0.4.1 applied

- Updated the vendored `ipe_web_kit` from v0.3.5 to v0.4.1 (`vendor/ipe_web_kit/`, tag `v0.4.1`, commit `3054c6c`).
- v0.3.4 and v0.3.5 added the `community` and `privacy` modules. Both are present but not enabled on the site.
- v0.4.0 added the `releases` module (release-note lint, merge, page generation, publish). It is vendored but not wired into this site.
- v0.4.1 changes in the vendored copy: time values without a timezone are read as KST (+09:00); the push-blackout check re-reads the clock just before push and queues the push if it falls in the window; overnight blackout windows are supported; a malformed queue file is reported instead of deleted.
- Site output is unchanged: the built `_site` files are identical before and after the update.
- Tests: 136 unittest cases pass; `home_sync`, `pages_sync` and `journal_sync` `--check` pass.

## 2026-11-11

### Web kit v0.3.5 applied

- Updated the vendored `ipe_web_kit` from v0.1.0 to v0.3.5 (`vendor/ipe_web_kit/`).
- The update adds the `community` and `privacy` modules. Both are present but not enabled on the site.
- Site output is unchanged: the built `_site` files are identical before and after the update.
