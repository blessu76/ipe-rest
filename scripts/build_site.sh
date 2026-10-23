#!/usr/bin/env bash
# 배포용 _site 만들기: 사이트에 필요 없는 개발 자원(scripts/ tests/ .github/ *.md .git*)은 제외한다.
# 사용: scripts/build_site.sh [출력폴더(기본 _site)]
set -euo pipefail
cd "$(dirname "$0")/.."
OUT="${1:-_site}"
rm -rf "$OUT"
mkdir -p "$OUT"
rsync -a \
  --exclude='/_site/' \
  --exclude='/scripts/' \
  --exclude='/tests/' \
  --exclude='/firebase/' \
  --exclude='/.github/' \
  --exclude='/.git' \
  --exclude='/.gitignore' \
  --exclude='*.md' \
  --exclude='.DS_Store' \
  ./ "$OUT"/
