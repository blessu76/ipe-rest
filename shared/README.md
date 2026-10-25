# shared/ — 전사 공통 모듈

## ipe-localtime.js (v1)
저널 게시 시각을 KST 로 기록하고, 화면에서는 보는 기기의 시간대로 바꿔 보이는 스크립트(`time[data-ipe-time]`). 의존성 없음.
- 정본은 이 파일. 다른 사이트(idle·still·draft·pawstcard)는 **바이트 그대로 복사**해 `</body>` 앞에 인라인 `<script>` 로 넣는다(외부 로드 금지).
- 정본 SHA-256 은 `ipe-localtime.sha256`. 바꾸면 머리 주석 버전(v2…)과 해시를 올리고 모든 사이트에 같은 날 퍼뜨린다.
- 테스트: `python3 -m unittest tests.test_localtime`
