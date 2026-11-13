#!/bin/zsh
set -e
cd -- "$(dirname "$0")"
export PATH="/opt/homebrew/bin:/usr/local/bin:$PATH"
export PYTHONUTF8=1
if [[ -x .venv/bin/python ]]; then
    .venv/bin/python app/setup_local.py --check
else
    python3 app/setup_local.py --check
fi
