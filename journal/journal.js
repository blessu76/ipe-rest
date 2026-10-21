/* ipe() journal — language chooser/redirect for x-default pages, EN/KO switch on the bilingual info pages (about/contact/privacy), GA4 (same property as the main page). */
(function () {
  // Translated pages (/journal/<lang>/…) are single-language static pages: no switch, <html lang> stays as served.
  if (document.querySelector('.langswitch')) {
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

    var btns = document.querySelectorAll('.langswitch button');
    for (var i = 0; i < btns.length; i++) {
      btns[i].addEventListener('click', function () {
        var l = this.getAttribute('data-lang') === 'ko' ? 'ko' : 'en';
        apply(l);
        try { localStorage.setItem('ipe_lang', l); } catch (e) {}  // saved only on an explicit user choice
      });
    }
  }

  // Header language select (generated pages): options are real URLs of this page in each available language.
  var picks = document.querySelectorAll('select[data-lang-select]');
  for (var m = 0; m < picks.length; m++) picks[m].addEventListener('change', function () {
    var o = this.options[this.selectedIndex];
    if (!o || !o.value) return;
    try { localStorage.setItem('ipe_lang', o.getAttribute('lang')); } catch (err) {}  // saved only on an explicit choice
    location.href = o.value;
  });

  // Journal pages: remember an explicit language choice (clicks on the language list).
  document.addEventListener('click', function (e) {
    var a = e.target.closest && e.target.closest('a.lg[hreflang]');
    if (!a) return;
    try { localStorage.setItem('ipe_lang', a.getAttribute('hreflang')); } catch (err) {}
  });

  // x-default chooser pages (/journal/ and /journal/<slug>/): go to the stored choice, else the browser language.
  // Without either (e.g. crawlers with no language), the page simply stays as the language list.
  if (document.documentElement.hasAttribute('data-chooser')) {
    var avail = {}, links = document.querySelectorAll('.choose-list a[hreflang]');
    for (var q = 0; q < links.length; q++) avail[links[q].getAttribute('hreflang')] = links[q].getAttribute('href');
    var want = null;
    try { want = localStorage.getItem('ipe_lang'); } catch (err) {}
    if (!want || !avail[want]) {
      want = null;
      try {
        var langs = navigator.languages || [navigator.language || ''];
        for (var n = 0; n < langs.length && !want; n++) {
          var c = (langs[n] || '').toLowerCase().split('-')[0];
          if (avail[c]) want = c;
        }
      } catch (err) {}
    }
    if (want && avail[want]) location.replace(avail[want]);
  }

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
    if (h === 'ipe.rest' || /\.ipe\.rest$/.test(h)) return;
    window.gtag('event', 'outbound_click', { link_url: a.href, link_domain: h, transport_type: 'beacon' });
  }
  document.addEventListener('click', trackOutbound);
  document.addEventListener('auxclick', trackOutbound);
})();
