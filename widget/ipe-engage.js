/* ipe() engage — shared like + comment widget (Firestore REST, no SDK, no login). One file for every ipe site.
 * Mount:  <section class="ipe-engage" data-site="ipe.rest" data-post="<slug>" data-lang="en"></section>
 *         + <link rel="stylesheet" href=".../ipe-engage.css"> + <script src=".../ipe-engage.js" defer></script>
 * Optional attributes: data-project / data-key (override the defaults below), data-theme="auto|light|dark".
 * Data model (see firebase/firestore.rules):  posts/{site}__{post} {site, post, count}  ·  posts/{site}__{post}/comments/{id} {name, text, createdAt}
 * Reading the article never depends on this file: every failure ends in a quiet hide or one short line. */
(function () {
  'use strict';
  var DEFAULTS = { project: 'ipe-web-REPLACE', key: 'REPLACE' };  // Firebase web config: public by design, protected by firestore.rules
  var PAGE = 20, GAP_MS = 30000;

  var T = {
    en: { like: 'Like', liked: 'Liked', comments: 'Comments', empty: 'No comments yet.', name: 'Nickname', text: 'Write a comment…', send: 'Post', sending: 'Posting…', sent: 'Thanks — your comment is up.', wait: 'Please wait a few seconds before posting again.', nolinks: 'Links are not allowed in comments.', invalid: 'Please add a nickname (up to 30 characters) and a comment (up to 500).', error: 'Could not post right now. Please try again later.', more: 'Show more', unavailable: 'Comments are unavailable right now.', hint: 'No account needed. Your nickname, comment and the time are shown publicly. No links, please.' },
    ko: { like: '좋아요', liked: '좋아요 완료', comments: '댓글', empty: '아직 댓글이 없습니다.', name: '닉네임', text: '댓글을 남겨 주세요…', send: '등록', sending: '등록 중…', sent: '감사합니다 — 댓글이 등록되었습니다.', wait: '잠시 후(몇 초 뒤) 다시 등록해 주세요.', nolinks: '댓글에는 링크를 넣을 수 없습니다.', invalid: '닉네임(30자 이내)과 댓글(500자 이내)을 입력해 주세요.', error: '지금은 등록할 수 없습니다. 잠시 후 다시 시도해 주세요.', more: '더 보기', unavailable: '지금은 댓글을 불러올 수 없습니다.', hint: '로그인이 필요 없습니다. 닉네임·댓글·작성 시각이 공개됩니다. 링크는 넣지 말아 주세요.' },
    ja: { like: 'いいね', liked: 'いいね済み', comments: 'コメント', empty: 'まだコメントはありません。', name: 'ニックネーム', text: 'コメントを書く…', send: '投稿', sending: '投稿中…', sent: 'ありがとうございます。コメントを投稿しました。', wait: '少し待ってからもう一度投稿してください。', nolinks: 'コメントにリンクは使えません。', invalid: 'ニックネーム(30文字以内)とコメント(500文字以内)を入力してください。', error: '現在投稿できません。しばらくしてからもう一度お試しください。', more: 'もっと見る', unavailable: '現在コメントを読み込めません。', hint: 'ログイン不要です。ニックネーム・コメント・投稿時刻が公開されます。リンクはご遠慮ください。' },
    zh: { like: '点赞', liked: '已点赞', comments: '评论', empty: '还没有评论。', name: '昵称', text: '写下你的评论…', send: '发布', sending: '发布中…', sent: '谢谢——评论已发布。', wait: '请稍等几秒再发布。', nolinks: '评论中不允许包含链接。', invalid: '请填写昵称(最多 30 个字符)和评论(最多 500 个字符)。', error: '暂时无法发布,请稍后再试。', more: '显示更多', unavailable: '暂时无法加载评论。', hint: '无需登录。昵称、评论和发布时间将公开显示。请不要放链接。' },
    es: { like: 'Me gusta', liked: 'Te gusta', comments: 'Comentarios', empty: 'Aún no hay comentarios.', name: 'Apodo', text: 'Escribe un comentario…', send: 'Publicar', sending: 'Publicando…', sent: 'Gracias: tu comentario ya está publicado.', wait: 'Espera unos segundos antes de volver a publicar.', nolinks: 'No se permiten enlaces en los comentarios.', invalid: 'Añade un apodo (máx. 30 caracteres) y un comentario (máx. 500).', error: 'No se pudo publicar ahora. Inténtalo más tarde.', more: 'Ver más', unavailable: 'Los comentarios no están disponibles ahora.', hint: 'No hace falta cuenta. Tu apodo, comentario y la hora se muestran públicamente. Sin enlaces, por favor.' },
    fr: { like: 'J’aime', liked: 'Aimé', comments: 'Commentaires', empty: 'Aucun commentaire pour l’instant.', name: 'Pseudo', text: 'Écrire un commentaire…', send: 'Publier', sending: 'Publication…', sent: 'Merci — votre commentaire est en ligne.', wait: 'Merci d’attendre quelques secondes avant de republier.', nolinks: 'Les liens ne sont pas autorisés dans les commentaires.', invalid: 'Ajoutez un pseudo (30 caractères max.) et un commentaire (500 max.).', error: 'Publication impossible pour le moment. Réessayez plus tard.', more: 'Voir plus', unavailable: 'Les commentaires sont indisponibles pour le moment.', hint: 'Aucun compte requis. Votre pseudo, votre commentaire et l’heure sont affichés publiquement. Pas de liens, merci.' },
    de: { like: 'Gefällt mir', liked: 'Gefällt dir', comments: 'Kommentare', empty: 'Noch keine Kommentare.', name: 'Spitzname', text: 'Kommentar schreiben…', send: 'Senden', sending: 'Wird gesendet…', sent: 'Danke – dein Kommentar ist online.', wait: 'Bitte warte ein paar Sekunden, bevor du erneut sendest.', nolinks: 'Links sind in Kommentaren nicht erlaubt.', invalid: 'Bitte gib einen Spitznamen (max. 30 Zeichen) und einen Kommentar (max. 500) ein.', error: 'Senden gerade nicht möglich. Bitte versuche es später erneut.', more: 'Mehr anzeigen', unavailable: 'Kommentare sind gerade nicht verfügbar.', hint: 'Kein Konto nötig. Spitzname, Kommentar und Uhrzeit sind öffentlich sichtbar. Bitte keine Links.' },
    pt: { like: 'Curtir', liked: 'Curtido', comments: 'Comentários', empty: 'Ainda não há comentários.', name: 'Apelido', text: 'Escreva um comentário…', send: 'Publicar', sending: 'Publicando…', sent: 'Obrigado — seu comentário foi publicado.', wait: 'Aguarde alguns segundos antes de publicar novamente.', nolinks: 'Links não são permitidos nos comentários.', invalid: 'Informe um apelido (até 30 caracteres) e um comentário (até 500).', error: 'Não foi possível publicar agora. Tente novamente mais tarde.', more: 'Ver mais', unavailable: 'Os comentários estão indisponíveis no momento.', hint: 'Não precisa de conta. Seu apelido, comentário e horário ficam públicos. Sem links, por favor.' },
    ru: { like: 'Нравится', liked: 'Вам нравится', comments: 'Комментарии', empty: 'Комментариев пока нет.', name: 'Ник', text: 'Напишите комментарий…', send: 'Отправить', sending: 'Отправка…', sent: 'Спасибо — комментарий опубликован.', wait: 'Подождите несколько секунд перед следующей отправкой.', nolinks: 'Ссылки в комментариях не допускаются.', invalid: 'Укажите ник (до 30 символов) и комментарий (до 500).', error: 'Сейчас не удалось отправить. Попробуйте позже.', more: 'Показать ещё', unavailable: 'Комментарии сейчас недоступны.', hint: 'Аккаунт не нужен. Ник, комментарий и время публикуются открыто. Без ссылок, пожалуйста.' },
    ar: { like: 'أعجبني', liked: 'أعجبك', comments: 'التعليقات', empty: 'لا توجد تعليقات بعد.', name: 'الاسم المستعار', text: 'اكتب تعليقًا…', send: 'نشر', sending: 'جارٍ النشر…', sent: 'شكرًا — تم نشر تعليقك.', wait: 'يرجى الانتظار بضع ثوانٍ قبل النشر مرة أخرى.', nolinks: 'الروابط غير مسموحة في التعليقات.', invalid: 'أدخل اسمًا مستعارًا (حتى 30 حرفًا) وتعليقًا (حتى 500 حرف).', error: 'تعذّر النشر الآن. حاول مرة أخرى لاحقًا.', more: 'عرض المزيد', unavailable: 'التعليقات غير متاحة حاليًا.', hint: 'لا حاجة إلى حساب. يظهر الاسم المستعار والتعليق ووقت النشر للجميع. من فضلك بلا روابط.' },
    hi: { like: 'पसंद', liked: 'पसंद किया', comments: 'टिप्पणियाँ', empty: 'अभी कोई टिप्पणी नहीं है।', name: 'उपनाम', text: 'टिप्पणी लिखें…', send: 'भेजें', sending: 'भेजा जा रहा है…', sent: 'धन्यवाद — आपकी टिप्पणी प्रकाशित हो गई।', wait: 'दोबारा भेजने से पहले कुछ सेकंड प्रतीक्षा करें।', nolinks: 'टिप्पणियों में लिंक की अनुमति नहीं है।', invalid: 'उपनाम (अधिकतम 30 अक्षर) और टिप्पणी (अधिकतम 500) लिखें।', error: 'अभी भेजा नहीं जा सका। कृपया बाद में पुनः प्रयास करें।', more: 'और दिखाएँ', unavailable: 'अभी टिप्पणियाँ उपलब्ध नहीं हैं।', hint: 'खाते की ज़रूरत नहीं। उपनाम, टिप्पणी और समय सार्वजनिक रूप से दिखेंगे। कृपया लिंक न डालें।' },
    id: { like: 'Suka', liked: 'Disukai', comments: 'Komentar', empty: 'Belum ada komentar.', name: 'Nama panggilan', text: 'Tulis komentar…', send: 'Kirim', sending: 'Mengirim…', sent: 'Terima kasih — komentar Anda sudah tampil.', wait: 'Tunggu beberapa detik sebelum mengirim lagi.', nolinks: 'Tautan tidak diizinkan di komentar.', invalid: 'Isi nama panggilan (maks. 30 karakter) dan komentar (maks. 500).', error: 'Tidak bisa mengirim sekarang. Coba lagi nanti.', more: 'Tampilkan lebih banyak', unavailable: 'Komentar sedang tidak tersedia.', hint: 'Tanpa akun. Nama panggilan, komentar, dan waktu ditampilkan secara publik. Mohon tanpa tautan.' }
  };

  function el(tag, cls, text) {
    var n = document.createElement(tag);
    if (cls) n.className = cls;
    if (text != null) n.textContent = text;
    return n;
  }
  function store(op, k, v) {
    try { return op === 'get' ? localStorage.getItem(k) : localStorage.setItem(k, v); } catch (e) { return null; }
  }
  function randomId() {
    var a = 'abcdefghijklmnopqrstuvwxyz0123456789', out = '', i;
    try {
      var u = new Uint8Array(20); crypto.getRandomValues(u);
      for (i = 0; i < 20; i++) out += a[u[i] % a.length];
    } catch (e) { for (i = 0; i < 20; i++) out += a[Math.floor(Math.random() * a.length)]; }
    return out;
  }
  var LINK = /(https?:|www\.|:\/\/)/i;  // keep in sync with firebase/firestore.rules

  function Engage(root) {
    var site = root.getAttribute('data-site'), post = root.getAttribute('data-post');
    var project = root.getAttribute('data-project') || DEFAULTS.project;
    var key = root.getAttribute('data-key') || DEFAULTS.key;
    if (!site || !post || /REPLACE/.test(project + key)) return;  // not configured -> stay empty (hidden by css)
    var lang = (root.getAttribute('data-lang') || document.documentElement.lang || 'en').toLowerCase().split('-')[0];
    var t = T[lang] || T.en;
    var pid = site + '__' + post;
    var db = 'projects/' + project + '/databases/(default)/documents';
    var base = 'https://firestore.googleapis.com/v1/' + db;
    var q = '?key=' + encodeURIComponent(key);
    var likeKey = 'ipe_like:' + pid, lastKey = 'ipe_comment_at:' + site;
    var theme = root.getAttribute('data-theme');
    if (theme) root.setAttribute('data-theme', theme);

    function api(method, path, body, extra) {
      return fetch(base + path + q + (extra || ''), {
        method: method,
        headers: body ? { 'Content-Type': 'application/json' } : undefined,
        body: body ? JSON.stringify(body) : undefined,
        credentials: 'omit', referrerPolicy: 'strict-origin-when-cross-origin'
      }).then(function (r) {
        if (r.status === 404 && method === 'GET') return null;
        if (!r.ok) throw new Error('http ' + r.status);
        return r.json();
      });
    }

    // ---- DOM ----
    root.setAttribute('lang', lang);
    root.textContent = '';
    var likeRow = el('div', 'ie-like');
    var likeBtn = el('button', 'ie-like-btn');
    likeBtn.type = 'button';
    var heart = el('span', 'ie-heart', '♥'); heart.setAttribute('aria-hidden', 'true');
    var likeLabel = el('span', 'ie-like-label', t.like);
    var likeCount = el('span', 'ie-like-count', '');
    likeCount.setAttribute('aria-live', 'polite');
    likeBtn.appendChild(heart); likeBtn.appendChild(likeLabel);
    likeRow.appendChild(likeBtn); likeRow.appendChild(likeCount);

    var h = el('h2', 'ie-title', t.comments);
    var list = el('ol', 'ie-list');
    var status = el('p', 'ie-status'); status.setAttribute('role', 'status');
    var moreBtn = el('button', 'ie-more', t.more); moreBtn.type = 'button'; moreBtn.hidden = true;

    var form = el('form', 'ie-form'); form.setAttribute('novalidate', '');
    var nameIn = el('input', 'ie-name'); nameIn.type = 'text'; nameIn.maxLength = 30; nameIn.placeholder = t.name;
    nameIn.setAttribute('aria-label', t.name); nameIn.autocomplete = 'nickname';
    var textIn = el('textarea', 'ie-text'); textIn.maxLength = 500; textIn.rows = 3; textIn.placeholder = t.text; textIn.setAttribute('aria-label', t.text);
    var trap = el('input', 'ie-trap'); trap.type = 'text'; trap.name = 'website'; trap.tabIndex = -1; trap.autocomplete = 'off'; trap.setAttribute('aria-hidden', 'true');
    var send = el('button', 'ie-send', t.send); send.type = 'submit';
    var hint = el('p', 'ie-hint', t.hint);
    var formMsg = el('p', 'ie-msg'); formMsg.setAttribute('role', 'status');
    var row = el('div', 'ie-row'); row.appendChild(hint); row.appendChild(send);
    form.appendChild(nameIn); form.appendChild(textIn); form.appendChild(trap); form.appendChild(row); form.appendChild(formMsg);

    root.appendChild(likeRow); root.appendChild(h); root.appendChild(list); root.appendChild(status); root.appendChild(moreBtn); root.appendChild(form);

    // ---- likes ----
    var count = 0, liked = store('get', likeKey) === '1';
    function paintLike() {
      likeBtn.setAttribute('aria-pressed', liked ? 'true' : 'false');
      likeBtn.disabled = liked;
      likeLabel.textContent = liked ? t.liked : t.like;
      likeCount.textContent = count > 0 ? String(count) : '';
    }
    paintLike();
    api('GET', '/posts/' + pid).then(function (d) {
      count = d && d.fields && d.fields.count ? parseInt(d.fields.count.integerValue, 10) || 0 : 0;
      paintLike();
    }).catch(function () {});
    likeBtn.addEventListener('click', function () {
      if (liked) return;
      liked = true; count += 1; paintLike();  // optimistic
      store('set', likeKey, '1');
      api('POST', ':commit', { writes: [{
        update: { name: db + '/posts/' + pid, fields: { site: { stringValue: site }, post: { stringValue: post } } },
        updateMask: { fieldPaths: ['site', 'post'] },
        updateTransforms: [{ fieldPath: 'count', increment: { integerValue: '1' } }]
      }] }).catch(function () {
        liked = false; count = Math.max(0, count - 1); paintLike();
        try { localStorage.removeItem(likeKey); } catch (e) {}
      });
    });

    // ---- comments ----
    var token = null, fmt;
    try { fmt = new Intl.DateTimeFormat(lang, { year: 'numeric', month: 'short', day: 'numeric' }); } catch (e) { fmt = null; }
    function addComment(doc) {
      var f = doc.fields || {};
      var li = el('li', 'ie-item');
      var meta = el('p', 'ie-meta');
      meta.appendChild(el('strong', 'ie-by', f.name ? f.name.stringValue : ''));
      var ts = f.createdAt && f.createdAt.timestampValue ? new Date(f.createdAt.timestampValue) : null;
      if (ts && !isNaN(ts) && fmt) { var tm = el('time', 'ie-time', fmt.format(ts)); tm.setAttribute('datetime', ts.toISOString()); meta.appendChild(tm); }
      li.appendChild(meta);
      li.appendChild(el('p', 'ie-body', f.text ? f.text.stringValue : ''));  // textContent only — never HTML
      list.appendChild(li);
    }
    function load() {
      moreBtn.disabled = true;
      return api('GET', '/posts/' + pid + '/comments', null, '&orderBy=createdAt&pageSize=' + PAGE + (token ? '&pageToken=' + encodeURIComponent(token) : '')).then(function (d) {
        var docs = (d && d.documents) || [];
        docs.forEach(function (x) { addComment(x); });
        token = d && d.nextPageToken || null;
        moreBtn.hidden = !token; moreBtn.disabled = false;
        status.textContent = list.children.length ? '' : t.empty;
      }).catch(function () {
        moreBtn.disabled = false;
        if (!list.children.length) status.textContent = t.unavailable;
      });
    }
    moreBtn.addEventListener('click', load);

    form.addEventListener('submit', function (e) {
      e.preventDefault();
      formMsg.textContent = ''; formMsg.className = 'ie-msg';
      function say(m, bad) { formMsg.textContent = m; formMsg.className = 'ie-msg' + (bad ? ' ie-bad' : ''); }
      var name = nameIn.value.trim(), text = textIn.value.trim();
      if (trap.value) { say(t.sent); form.reset(); return; }  // honeypot: pretend success, store nothing
      if (!name || name.length > 30 || !text || text.length > 500) return say(t.invalid, true);
      if (LINK.test(name) || LINK.test(text)) return say(t.nolinks, true);
      var last = parseInt(store('get', lastKey) || '0', 10) || 0;
      if (Date.now() - last < GAP_MS) return say(t.wait, true);
      send.disabled = true; send.textContent = t.sending;
      var id = randomId();
      api('POST', ':commit', { writes: [{
        update: { name: db + '/posts/' + pid + '/comments/' + id, fields: { name: { stringValue: name }, text: { stringValue: text } } },
        updateTransforms: [{ fieldPath: 'createdAt', setToServerValue: 'REQUEST_TIME' }],
        currentDocument: { exists: false }
      }] }).then(function () {
        store('set', lastKey, String(Date.now()));
        addComment({ fields: { name: { stringValue: name }, text: { stringValue: text }, createdAt: { timestampValue: new Date().toISOString() } } });
        status.textContent = '';
        textIn.value = '';
        say(t.sent);
      }).catch(function () { say(t.error, true); }).then(function () { send.disabled = false; send.textContent = t.send; });
    });

    load();
  }

  function boot() {
    var nodes = document.querySelectorAll('[data-ipe-engage],.ipe-engage');
    Array.prototype.forEach.call(nodes, function (root) {
      if (root.getAttribute('data-ie-init')) return;
      root.setAttribute('data-ie-init', '1');
      var start = function () { try { Engage(root); } catch (e) { root.textContent = ''; } };
      if (window.IntersectionObserver) {  // lazy: only when the reader nears the end of the article
        var io = new IntersectionObserver(function (es) {
          if (es.some(function (x) { return x.isIntersecting; })) { io.disconnect(); start(); }
        }, { rootMargin: '600px 0px' });
        io.observe(root);
      } else start();
    });
  }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', boot); else boot();
})();
