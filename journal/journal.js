/* ipe() journal — EN/KO switch + GA4 (same property as the main page). */
(function () {
  var root = document.documentElement;
  var titles = {};
  var tEn = document.querySelector('meta[name="ipe:title-en"]');
  var tKo = document.querySelector('meta[name="ipe:title-ko"]');
  if (tEn) titles.en = tEn.content;
  if (tKo) titles.ko = tKo.content;

  function apply(lang) {
    if (lang !== 'ko') lang = 'en';
    root.setAttribute('lang', lang);
    if (titles[lang]) document.title = titles[lang];
    var btns = document.querySelectorAll('.langswitch button');
    for (var i = 0; i < btns.length; i++) {
      btns[i].setAttribute('aria-pressed', btns[i].getAttribute('data-lang') === lang ? 'true' : 'false');
    }
    try { localStorage.setItem('ipe_lang', lang); } catch (e) {}
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
  apply(initial);

  var btns = document.querySelectorAll('.langswitch button');
  for (var i = 0; i < btns.length; i++) {
    btns[i].addEventListener('click', function () { apply(this.getAttribute('data-lang')); });
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
