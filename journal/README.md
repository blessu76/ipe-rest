# ipe() journal — 운영 절차

`ipe.rest/journal/` — 정적 HTML 저널. 주 1회 1편. 디자인은 메인(`/index.html`)의 v2 토큰을 `journal.css` 로 공유한다(새 색 금지, 옛 금색 `#c9a84c` 금지).
언어: 글 하나에 EN/KO 블록을 함께 두고 `journal.js` 가 `?lang=` > 저장값(`ipe_lang`) > 브라우저 언어 순으로 고른다(ko 외에는 en).

## 새 글 추가 (5단계)
1. `journal/_TEMPLATE.html` 을 `journal/<YYYY-MM-DD>-<slug>/index.html` 로 복사하고 `{{…}}` 를 모두 채운다. `<meta name="robots">` 를 `index, follow, max-image-preview:large, max-snippet:-1, max-video-preview:-1` 로 되돌린다(템플릿은 noindex).
   - 본문 600~1,000자 안팎, EN/KO 둘 다. BlogPosting JSON-LD(`headline`·`datePublished`)·og·canonical 확인.
2. `journal/index.html` 의 `<ul class="post-list">` 맨 위에 카드 `<li>` 추가 + 상단 JSON-LD `blogPost` 배열에 항목 추가.
3. `sitemap.xml` 에 새 글 `<url>` 추가, `/journal/` 의 `lastmod` 갱신.
4. `llms.txt` 의 `## Journal` 에 한 줄 추가.
5. `sw.js` 의 `CACHE` 버전 +1. CSS/JS 를 바꿨다면 `journal.css?v=` · `journal.js?v=` 도 +1 (모든 journal 페이지의 링크 일괄).

## 확인
320 / 375 / 768 / 1280 폭에서 가로 스크롤 0, 404 0, EN·KO 둘 다. 푸시는 ship 담당만.

## 글에 쓰지 않는 것
미발표 기획(S1A2 이후 앨범 등), 내부 수치(구독자·매출 등), 시크릿, 개인정보.

## 다음 글 후보 5개 (사실 근거: 공개된 사실만)
1. **dear(you); vol.1 — 열 통의 편지** : 앨범의 감정 아크(공감→이해→불안→안심→쉼→연결→감사→인정→희망→평온). 근거 `studio/lyrics/albums/dear-you_album.md`, `llms.txt`.
2. **late_night.lofi — 퇴근길의 소리** : 야근 후 퇴근길 시리즈, 싱글 「still compiling」(N-001). 근거 `studio/README.md`(콘텐츠 시리즈), `llms.txt`(Releases).
3. **AI로 음악을 만든다는 것, 그리고 숨기지 않는 이유** : Suno 사용 공개 + 가사·콘셉트는 직접 쓰는 방식. 근거 `llms.txt`(Key facts), `_ipe/brand/BRAND.md`(차별점 「AI 제작 투명 공개」).
4. **‘ipe. be still’ — 모든 곡 끝의 한 호흡** : 시그니처 가사의 규칙(맨 끝, 속삭임, 영어 고정). 근거 `studio/lyrics/INDEX.md`「공통 브랜드 원칙」, `studio/README.md`.
5. **코드 에디터 같은 고요함 — ipe() 의 비주얼 언어** : 페이퍼-크림·잉크·Lora/Inter/JetBrains Mono, `//` 주석 보이스. 근거 `_ipe/brand/BRAND.md`(비주얼 아이덴티티 v2), `_ipe/brand/design-system/`.
