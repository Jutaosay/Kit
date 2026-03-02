#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

if [[ ! -d .venv ]]; then
  echo "[x] .venv 不存在，请先创建：python3 -m venv .venv"
  exit 1
fi

source .venv/bin/activate
python -m pip install -r requirements.txt >/dev/null
python -m py_compile kit.py

echo "[ok] venv 内测试通过"
