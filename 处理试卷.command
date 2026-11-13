#!/bin/zsh
set -e
cd -- "$(dirname "$0")"
export PATH="/opt/homebrew/bin:/usr/local/bin:$PATH"
export PYTHONUTF8=1
if [[ ! -x .venv/bin/python ]]; then
    python3 app/setup_local.py --install
fi
.venv/bin/python app/exam_print.py --open "$@"
echo "已完成。打印文件在 output/最新结果，原文件在已处理。"
