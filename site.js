/* ipe.rest site.js v1 · 2026-10-18
   1) Language: EN/KO static pages. A saved choice (localStorage ipe_lang) or an old ?lang=ko link sends English pages to /ko/.
   2) Drawer (<=760): close button receives focus on open; Esc / scrim / resize close; Tab is trapped. */
(function () {
  var sel = document.querySelector('select.lang');
  var KEY = 'ipe_lang';
  function get() { try { return localStorage.getItem(KEY); } catch (e) { return null; } }
  function set(v) { try { localStorage.setItem(KEY, v); } catch (e) {} }
  if (sel) {
    var isKo = document.documentElement.lang === 'ko';
    if (!isKo) {
      var q = (location.search.match(/[?&]lang=([a-z]{2})/) || [])[1];
      if (q === 'ko' || (!q && get() === 'ko')) { location.replace(sel.getAttribute('data-ko') + location.hash); return; }
    }
    sel.addEventListener('change', function () {
      set(sel.value);
      location.href = sel.getAttribute('data-' + sel.value) + location.hash;
    });
  }
})();

(function () {
  var btn = document.querySelector('.menu-btn'), drawer = document.getElementById('drawer'), scrim = document.querySelector('.scrim');
  if (!btn || !drawer) return;
  var close = drawer.querySelector('.drawer-close');
  function focusables() { return drawer.querySelectorAll('a[href],button'); }
  function open() {
    drawer.classList.add('is-open'); scrim.classList.add('is-open');
    drawer.removeAttribute('inert'); drawer.setAttribute('aria-hidden', 'false');
    btn.setAttribute('aria-expanded', 'true'); document.body.classList.add('drawer-lock');
    /* visibility transition: the drawer is not focusable until it is rendered, so retry for ~0.5s */
    var tries = 0;
    (function focusClose() {
      close.focus();
      if (document.activeElement !== close && drawer.classList.contains('is-open') && tries++ < 12) setTimeout(focusClose, 40);
    })();
  }
  function shut(restore) {
    drawer.classList.remove('is-open'); scrim.classList.remove('is-open');
    drawer.setAttribute('inert', ''); drawer.setAttribute('aria-hidden', 'true');
    btn.setAttribute('aria-expanded', 'false'); document.body.classList.remove('drawer-lock');
    if (restore !== false) btn.focus();
  }
  btn.addEventListener('click', open);
  close.addEventListener('click', function () { shut(); });
  scrim.addEventListener('click', function () { shut(); });
  document.addEventListener('keydown', function (e) {
    if (!drawer.classList.contains('is-open')) return;
    if (e.key === 'Escape') { shut(); return; }
    if (e.key === 'Tab') {
      var f = focusables(), first = f[0], last = f[f.length - 1];
      if (e.shiftKey && document.activeElement === first) { e.preventDefault(); last.focus(); }
      else if (!e.shiftKey && document.activeElement === last) { e.preventDefault(); first.focus(); }
    }
  });
  window.matchMedia('(min-width:761px)').addEventListener('change', function (m) { if (m.matches) shut(false); });
})();
