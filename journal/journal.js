/* ipe() journal — x-default chooser (redirect = kit ipe-lang.js; here ?lang= is remembered), EN/KO switch on the bilingual info pages (about/contact/privacy), GA4 (same property as the main page). */
(function () {
  // Translated pages (/journal/<lang>/…) are single-language static pages: no switch, <html lang> stays as served.
  if (document.querySelector('.langswitch')) {  // buttons (source template) or the header select (about/contact/privacy)
    var root = document.documentElement;
    var titles = {};
    var tEn = document.querySelector('meta[name="ipe:title-en"]');
    var tKo = document.querySelector('meta[name="ipe:title-ko"]');
    if (tEn) titles.en = tEn.content;
    if (tKo) titles.ko = tKo.content;

    function apply(lang) {
      if (lang !== 'ko') lang = 'en';
      root.setAttribute('lang', lang);
    var jl = document.querySelectorAll('a[href="/journal/en/"],a[href="/journal/ko/"]');
    for (var k = 0; k < jl.length; k++) jl[k].setAttribute('href', '/journal/' + lang + '/');
      if (titles[lang]) document.title = titles[lang];
      var btns = document.querySelectorAll('.langswitch button');
      for (var i = 0; i < btns.length; i++) {
        btns[i].setAttribute('aria-pressed', btns[i].getAttribute('data-lang') === lang ? 'true' : 'false');
      }
      var pick = document.querySelector('select[data-lang-pick]');
      if (pick) pick.value = lang;
    }

    var urlLang = null, stored = null, initial = 'en';
    try { urlLang = new URLSearchParams(location.search).get('lang'); } catch (e) {}
    try { stored = localStorage.getItem('ipe_lang'); } catch (e) {}
    try {
      var list = navigator.languages || [navigator.language || ''];
      var first = (list[0] || '').toLowerCase().split('-')[0];
      if (first === 'ko') initial = 'ko';
    } catch (e) {}
    // priority: ?lang= > stored > browser > en  (non-ko values fall back to en)
    if (urlLang) initial = urlLang === 'ko' ? 'ko' : 'en';
    else if (stored) initial = stored === 'ko' ? 'ko' : 'en';
    apply(initial);  // initial render never writes localStorage (a stored value like "ja" stays untouched)

    var pk = document.querySelector('select[data-lang-pick]');
    if (pk) pk.addEventListener('change', function () {
      var l = this.value === 'ko' ? 'ko' : 'en';
      apply(l);
      try { localStorage.setItem('ipe_lang', l); } catch (e) {}  // saved only on an explicit user choice
    });
    var btns = document.querySelectorAll('.langswitch button');
    for (var i = 0; i < btns.length; i++) {
      btns[i].addEventListener('click', function () {
        var l = this.getAttribute('data-lang') === 'ko' ? 'ko' : 'en';
        apply(l);
        try { localStorage.setItem('ipe_lang', l); } catch (e) {}  // saved only on an explicit user choice
      });
    }
  }

  // Journal pages: remember an explicit language choice (clicks on the language list).
  document.addEventListener('click', function (e) {
    var a = e.target.closest && e.target.closest('a.lg[hreflang]');
    if (!a) return;
    try { localStorage.setItem('ipe_lang', a.getAttribute('hreflang')); } catch (err) {}
  });

  // x-default chooser pages: the redirect itself is the web kit's /shared/ipe-lang.js (saved ipe_lang choice > browser language > en;
  // crawlers never redirected). Here only `?lang=xx` (old links) is remembered, so ipe-lang.js then sends the visitor there.
  if (document.documentElement.hasAttribute('data-chooser')) {
    try {
      var ql = String(new URLSearchParams(location.search).get('lang') || '').toLowerCase().split(/[-_]/)[0];
      if (ql && document.querySelector('.choose-list a[hreflang="' + ql + '"], .choose-list a[hreflang^="' + ql + '-"]')) {
        var a0 = document.querySelector('.choose-list a[hreflang^="' + ql + '"]');
        localStorage.setItem('ipe_lang', a0.getAttribute('hreflang'));
      }
    } catch (err) {}
  }

  if (/^(localhost|127\.0\.0\.1|\[::1\])$/.test(location.hostname)) return;
  // GA4 — same measurement ID as index.html
  var GA = 'G-XG4BH800J0';
  var s = document.createElement('script');
  s.async = true; s.src = 'https://www.googletagmanager.com/gtag/js?id=' + GA;
  document.head.appendChild(s);
  window.dataLayer = window.dataLayer || [];
  window.gtag = function () { window.dataLayer.push(arguments); };
  window.gtag('js', new Date());
  window.gtag('config', GA);
  function trackOutbound(e) {
    if (e.type === 'auxclick' && e.button !== 1) return;
    var a = e.target.closest && e.target.closest('a[href^="http"]');
    if (!a) return;
    var h = a.hostname;
    if (h === location.hostname || h === 'ipe.rest' || /\.ipe\.rest$/.test(h)) return;
    window.gtag('event', 'outbound_click', { link_url: a.href, link_domain: h, transport_type: 'beacon' });
  }
  document.addEventListener('click', trackOutbound);
  document.addEventListener('auxclick', trackOutbound);
})();
