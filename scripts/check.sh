#!/usr/bin/env bash
# 전체 점검: 생성물 동기화(--check) · 저널 카피 검수(Iris) · 단위 시험. 하나라도 실패하면 non-zero.
set -euo pipefail
cd "$(dirname "$0")/.."
python3 scripts/home_sync.py --check
python3 scripts/pages_sync.py --check
python3 scripts/journal_sync.py --check
python3 scripts/journal_check.py
python3 -m unittest discover -s tests
