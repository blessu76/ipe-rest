# shared/ — 전사 공통 모듈

## ipe-localtime.js (v2)
저널 게시 시각을 KST 로 기록하고, 화면에서는 보는 기기의 시간대로 바꿔 보이는 스크립트(`time[data-ipe-time]`). 의존성 없음.
- 정본은 이 파일. 다른 사이트(idle·still·draft·pawstcard)는 **바이트 그대로 복사**해 `</body>` 앞에 인라인 `<script>` 로 넣는다(외부 로드 금지).
- 정본 SHA-256(hex)은 `ipe-localtime.sha256`. 바꾸면 머리 주석 버전과 해시를 올리고 모든 사이트에 같은 날 퍼뜨린다.
- v2: `datetime` 이 `YYYY-MM-DDTHH:MM(:SS)?` + 오프셋(`+09:00`·`+0900`·`Z`) 형식이 아니면 건너뛴다(정적 글자 유지). 달력·숫자는 그레고리력·라틴 숫자로 고정(th 불기·fa 페르시아력 방지).

### 삽입 규칙
- **줄바꿈 규칙(하나로 고정)**: `<script>` 바로 뒤와 `</script>` 바로 앞에 **줄바꿈·공백을 더하지 않는다.** 인라인 텍스트 = 파일 바이트 전체(끝의 `\n` 한 개 포함) 그대로. 즉 `<script>/* ipe-localtime v2 …` 로 시작해 마지막 `})();` + `\n` 바로 다음에 `</script>`.
- **CSP**(`script-src` 를 쓰는 사이트): `'sha256-VzJkSd31BQ6rrdE5TWnrKw9hyI8ITsg+5K/2/K0PdLg='` — 위 규칙대로 감싼 인라인 텍스트(= 파일 바이트)의 base64 SHA-256. hex 는 `57326449ddf5050eabadd1394d69eb2b0f61c88f084ec83ee4aff6fcad0f74b8`.
- `<time data-ipe-time datetime="…+09:00">` 안은 **텍스트만**(자식 요소 금지 — 변환 시 textContent 가 통째로 바뀐다).
- JS 로 나중에 그린 `<time>` 은 대상이 아니다(스크립트는 실행 시점에 한 번만 훑는다).
- Cloudflare minify / Rocket Loader / Auto Minify 가 인라인 스크립트 바이트를 바꾸면 CSP 해시가 깨진다 — 해당 사이트는 JS minify·Rocket Loader 를 끄거나 `data-cfasync="false"` 를 쓰고, 배포 후 해시를 확인한다.
- 테스트: `python3 -m unittest tests.test_localtime` (node 없으면 동작 시험은 skip)
