/* ipe-localtime v1 · 정본 ipe-rest/shared/ipe-localtime.js · 사본은 바이트 그대로 */
/* time[data-ipe-time] 의 datetime(+09:00)을 보는 기기 시간대로 바꿔 보인다. 실패하면 정적 KST 글자를 그대로 둔다. */
(function () {
  try {
    var zone = Intl.DateTimeFormat().resolvedOptions().timeZone;
    var names = { 'Asia/Seoul': 'KST', 'Asia/Tokyo': 'JST' };
    var fmt = new Intl.DateTimeFormat(document.documentElement.lang || 'en', {
      year: 'numeric', month: 'short', day: 'numeric',
      hour: '2-digit', minute: '2-digit', hourCycle: 'h23', timeZoneName: 'short'
    });
    var els = document.querySelectorAll('time[data-ipe-time]');
    for (var i = 0; i < els.length; i++) {
      var el = els[i];
      try {
        if (el.hasAttribute('data-ipe-time-done')) continue;
        var d = new Date(el.getAttribute('datetime'));
        if (isNaN(d.getTime())) continue;
        var text = fmt.formatToParts(d).map(function (p) {
          return p.type === 'timeZoneName' && names[zone] ? names[zone] : p.value;
        }).join('');
        if (!el.getAttribute('title')) el.setAttribute('title', el.textContent.trim());
        el.textContent = text;
        el.setAttribute('data-ipe-time-done', '');
      } catch (e) {}
    }
  } catch (e) {}
})();
