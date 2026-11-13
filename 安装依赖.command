#!/bin/zsh
set -e
cd -- "$(dirname "$0")"
export PATH="/opt/homebrew/bin:/usr/local/bin:$PATH"
export PYTHONUTF8=1
python3 app/setup_local.py --install
echo "本地环境已准备好。以后双击处理试卷.command。"
