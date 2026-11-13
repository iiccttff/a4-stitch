from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]

# 中文日志也必须能写入英文Windows/CI的重定向输出，尤其不能在归档后因打印日志崩溃。
if sys.platform in ('win32','darwin'):
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, 'reconfigure'):
            stream.reconfigure(encoding='utf-8', errors='backslashreplace')
