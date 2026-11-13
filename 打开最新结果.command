#!/bin/zsh
set -e
cd -- "$(dirname "$0")"
export PATH="/opt/homebrew/bin:/usr/local/bin:$PATH"
export PYTHONUTF8=1
if [[ -d output/最新结果 ]]; then
    open output/最新结果
else
    echo "还没有处理结果，请先运行处理试卷.command。"
fi
